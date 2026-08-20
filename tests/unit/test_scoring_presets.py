import json
from decimal import Decimal
from pathlib import Path


def test_pilot_scoring_presets_have_complete_unit_weights() -> None:
    root = Path(__file__).resolve().parents[2] / "assets/scoring/presets"
    expected = {"trend", "demand", "competition", "margin", "supply", "shop_fit", "confidence"}
    for path in root.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        weights = {key: Decimal(value) for key, value in payload["weights"].items()}
        assert set(weights) == expected
        assert sum(weights.values(), Decimal("0")) == Decimal("1")
