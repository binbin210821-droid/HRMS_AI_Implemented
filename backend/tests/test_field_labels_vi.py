from app.core.field_labels_vi import (
    FIELD_LABELS_VI,
    sanitize_ai_text,
    translate_metrics_to_vietnamese,
)


def test_translation_uses_vietnamese_labels_for_nested_metrics() -> None:
    data = {
        "tasks_completed": 4,
        "quality_score": 80,
        "performance_score": 86.0,
        "alerts": [{"trigger_reason": "task_volume"}],
    }

    translated = translate_metrics_to_vietnamese(data)

    assert "Số công việc hoàn thành: 4" in translated
    assert "Điểm chất lượng công việc: 80" in translated
    assert "Điểm hiệu suất: 86.0" in translated
    assert "tasks_completed" not in translated
    assert "trigger_reason" not in translated


def test_provider_output_is_sanitized_even_when_it_contains_raw_fields() -> None:
    output = sanitize_ai_text("tasks_completed tăng, quality_score cần theo dõi")

    assert output == "Số công việc hoàn thành tăng, Điểm chất lượng công việc cần theo dõi"
    assert all(raw_name not in output for raw_name in FIELD_LABELS_VI)
