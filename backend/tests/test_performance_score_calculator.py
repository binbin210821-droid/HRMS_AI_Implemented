import pytest

from app.services.performance_score_calculator import PerformanceScoreCalculator


def test_calculates_the_reference_score() -> None:
    assert PerformanceScoreCalculator.task_volume_score(4) == 100.0
    assert PerformanceScoreCalculator.calculate(4, 80) == 86.0


def test_caps_task_volume_and_total_score_at_100() -> None:
    assert PerformanceScoreCalculator.task_volume_score(6) == 100.0
    assert PerformanceScoreCalculator.calculate(10, 100) == 100.0


@pytest.mark.parametrize("tasks_completed", [-1, -10])
def test_rejects_negative_task_count(tasks_completed: int) -> None:
    with pytest.raises(ValueError):
        PerformanceScoreCalculator.task_volume_score(tasks_completed)


def test_rejects_quality_outside_range() -> None:
    with pytest.raises(ValueError):
        PerformanceScoreCalculator.calculate(4, 101)
