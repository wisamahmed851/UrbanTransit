"""Task-appropriate operational quality metrics."""

from python_pipeline.phase7_python_models import cls_scores, occupancy_scores


def test_delay_within_one_adjacent_band_accuracy():
    scores = cls_scores(
        ["On Time", "Minor", "Moderate", "Severe"],
        ["Minor", "Moderate", "Severe", "Moderate"],
    )
    assert scores["accuracy"] == 0.0
    assert scores["within_one_band_accuracy"] == 1.0


def test_occupancy_within_twenty_percentage_points_accuracy():
    scores = occupancy_scores([0.20, 0.50, 0.90, 1.20], [0.30, 0.71, 0.72, 1.01])
    assert scores["within_20pp_accuracy"] == 0.75
