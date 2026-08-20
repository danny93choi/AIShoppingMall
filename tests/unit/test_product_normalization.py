from commerce_agent.domain.products.normalization import (
    ProductNormalizer,
    is_near_duplicate,
    normalize_text,
)


def test_normalize_text_handles_case_spacing_and_punctuation() -> None:
    assert normalize_text("  ACME—T600  텀블러!! ") == "acme t600 텀블러"


def test_dedupe_key_uses_brand_model_and_critical_attributes() -> None:
    normalizer = ProductNormalizer()
    left = normalizer.normalize(
        "Acme T600 텀블러", {"brand": "Acme", "model": "T600", "capacity_ml": 600}
    )
    right = normalizer.normalize(
        "ACME 보온 텀블러 T600", {"brand": "acme", "model": "t600", "capacity_ml": 600}
    )
    variation = normalizer.normalize(
        "Acme T600 텀블러", {"brand": "Acme", "model": "T600", "capacity_ml": 900}
    )
    assert left.dedupe_key == right.dedupe_key
    assert left.dedupe_key != variation.dedupe_key


def test_near_duplicate_rule() -> None:
    assert is_near_duplicate("Novi L10 테이블 램프", "Novi L10 테이블램프")
    assert not is_near_duplicate("Novi L10 램프", "Pico B2 크로스백")
