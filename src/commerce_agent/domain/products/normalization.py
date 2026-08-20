import hashlib
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

SPACE_PATTERN = re.compile(r"\s+")
NON_WORD_PATTERN = re.compile(r"[^\w가-힣]+", re.UNICODE)
MODEL_PATTERN = re.compile(r"\b(?=[A-Z0-9-]*\d)[A-Z][A-Z0-9-]{1,15}\b", re.IGNORECASE)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = NON_WORD_PATTERN.sub(" ", value)
    return SPACE_PATTERN.sub(" ", value).strip()


@dataclass(frozen=True, slots=True)
class NormalizedProduct:
    canonical_name: str
    normalized_title: str
    brand: str | None
    model: str | None
    category_id: str
    attributes: dict[str, Any]
    dedupe_key: str


class ProductNormalizer:
    def normalize(self, title: str, metadata: dict[str, Any]) -> NormalizedProduct:
        normalized_title = normalize_text(title)
        brand_value = metadata.get("brand")
        brand = str(brand_value).strip() if brand_value else None
        model_value = metadata.get("model")
        match = MODEL_PATTERN.search(title)
        model = (
            str(model_value).strip().upper()
            if model_value
            else (match.group(0).upper() if match else None)
        )
        category_id = self._category_for(normalized_title)
        attributes = {
            key: value
            for key, value in metadata.items()
            if key not in {"brand", "model"} and value is not None
        }
        critical = "|".join(f"{key}={attributes[key]}" for key in sorted(attributes))
        identity = "|".join(
            [
                normalize_text(brand or "unknown"),
                normalize_text(model or normalized_title),
                category_id,
                critical,
            ]
        )
        dedupe_key = hashlib.sha256(identity.encode()).hexdigest()
        canonical = " ".join(value for value in (brand, model) if value) or title.strip()
        return NormalizedProduct(
            canonical_name=canonical,
            normalized_title=normalized_title,
            brand=brand,
            model=model,
            category_id=category_id,
            attributes=attributes,
            dedupe_key=dedupe_key,
        )

    @staticmethod
    def _category_for(title: str) -> str:
        rules = {
            "home.kitchen.drinkware": ("텀블러", "머그", "mug", "tumbler"),
            "home.bath.towels": ("타월", "수건", "towel"),
            "home.lighting.table_lamps": ("램프", "lamp"),
            "fashion.bags.crossbody": ("크로스백", "크로스 백", "crossbody"),
        }
        for category, keywords in rules.items():
            if any(keyword in title for keyword in keywords):
                return category
        return "uncategorized"


def is_near_duplicate(left: str, right: str, threshold: float = 0.88) -> bool:
    left_normalized = normalize_text(left)
    right_normalized = normalize_text(right)
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    similarity = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return overlap >= 0.7 or similarity >= threshold
