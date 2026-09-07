class PerformanceScoreCalculator:
    """Bộ tính điểm thuần toán học, không phụ thuộc database hay framework."""

    STANDARD_DAILY_TASKS = 4
    MAX_TASK_VOLUME_MULTIPLIER = 1.5
    MAX_SCORE = 100.0

    @classmethod
    def task_volume_score(cls, tasks_completed: int) -> float:
        if tasks_completed < 0:
            raise ValueError("Số công việc hoàn thành không được âm")
        raw_score = min(tasks_completed / cls.STANDARD_DAILY_TASKS, cls.MAX_TASK_VOLUME_MULTIPLIER)
        return min(raw_score * 100, cls.MAX_SCORE)

    @classmethod
    def calculate(cls, tasks_completed: int, quality_score: float) -> float:
        if not 0 <= quality_score <= 100:
            raise ValueError("Điểm chất lượng phải nằm trong khoảng 0-100")
        volume_score = cls.task_volume_score(tasks_completed)
        return round((quality_score * 0.7) + (volume_score * 0.3), 2)
