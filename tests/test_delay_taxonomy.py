"""The generated delay target must remain an explicit, four-label contract."""

from config import settings
from src.services.model_serving import delay_band_description, delay_bands_match_model


def test_delay_severity_contract_is_complete_and_excludes_major():
    contract = settings.delay_severity_contract()
    assert contract["labels"] == ["On Time", "Minor", "Moderate", "Severe"]
    assert contract["cutpoints_minutes"] == [5, 10, 20]
    assert contract["excluded_label"] == "Major"
    assert "Major" not in contract["labels"]


def test_serving_uses_the_configured_delay_taxonomy():
    assert delay_bands_match_model() is True
    description = delay_band_description()
    assert "On Time < 5 min" in description
    assert "Severe >= 20 min" in description
    assert "Major is not a generated label" in description
