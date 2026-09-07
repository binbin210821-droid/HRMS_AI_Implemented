from app.models.overload import OverloadLogDocument, WorkloadCandidateResponse
from app.repositories.overload_repository import OverloadRepository


class WorkloadRebalancer:
    """Finds same-department employees with spare capacity and stable quality."""

    def __init__(self, repository: OverloadRepository) -> None:
        self.repository = repository

    async def suggest(self, overload_log: OverloadLogDocument) -> list[WorkloadCandidateResponse]:
        return await self.repository.find_rebalance_candidates(
            overload_log.department_id,
            overload_log.date,
            overload_log.employee_id,
        )

    async def suggest_many(
        self, overload_logs: list[OverloadLogDocument]
    ) -> dict[tuple[object, object], list[WorkloadCandidateResponse]]:
        candidates_by_group: dict[tuple[object, object], list[WorkloadCandidateResponse]] = {}
        for overload_log in overload_logs:
            group = (overload_log.department_id, overload_log.date)
            if group not in candidates_by_group:
                candidates_by_group[group] = (
                    await self.repository.find_rebalance_candidates_for_group(*group)
                )
        return candidates_by_group


__all__ = ["WorkloadRebalancer"]
