from scripts.seed_performance_data import metric_values


def test_metric_values_supports_non_numeric_employee_code() -> None:
    tasks_completed, quality_score, note = metric_values("NGB", 4)

    assert 2 <= tasks_completed <= 4
    assert 78 <= quality_score <= 95
    assert note is None


def test_metric_values_is_deterministic_for_same_employee_and_day() -> None:
    assert metric_values("NGB", 4) == metric_values("NGB", 4)
