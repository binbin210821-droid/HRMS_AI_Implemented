import sys
from pathlib import Path

from fastapi.routing import APIRoute

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app


def dependency_names(dependant) -> set[str]:
    names: set[str] = set()
    for dependency in dependant.dependencies:
        call = dependency.call
        if call is not None:
            names.add(getattr(call, "__name__", ""))
        names.update(dependency_names(dependency))
    return names

openapi = app.openapi()
paths = list(openapi["paths"])
security_schemes = openapi["components"]["securitySchemes"]
assert security_schemes["CookieAuth"]["in"] == "cookie"
assert security_schemes["BearerAuth"]["scheme"] == "bearer"
assert security_schemes["BearerAuth"]["description"].startswith("Deprecated")
assert "/api/health" in paths
assert "/api/auth/login" in paths
assert "/api/auth/me" in paths
assert "/api/auth/logout" in paths
assert "/api/v1/auth/login" in paths
assert "/api/v1/auth/me" in paths
assert "/api/v1/auth/logout" in paths
assert "/api/departments" in paths
assert "/api/departments/{department_id}" in paths
assert "/api/employees" in paths
assert "/api/employees/{employee_id}" in paths
assert "/api/performance/analytics/employee/{employee_id}" in paths
assert "/api/performance/analytics/department/{department_id}" in paths
assert "/api/performance/analytics/company" in paths
assert "/api/alerts" in paths
assert "/api/alerts/scan" in paths
assert "/api/alerts/{alert_id}/resolve" in paths
assert "/api/threshold-configs" in paths
assert "/api/threshold-configs/{config_id}/approve" in paths
assert "/api/overload" in paths
assert "/api/overload/scan" in paths
assert "/api/v1/alerts/{alert_id}" in paths
assert "/api/v1/threshold-configs/{config_id}" in paths
assert "/api/v1/overload/scans" in paths
assert "/api/v1/attachments/upload-sessions/{session_id}" in paths
assert "/api/v1/coordination/alerts/{alert_id}/plans" in paths
assert "/api/v1/coordination/directives/{directive_id}/fulfillment" in paths
assert "/api/v1/coordination/department-directives/{directive_id}/acknowledgement" in paths
assert "/api/v1/coordination/department-directives/{directive_id}/submission" in paths
assert "/api/v1/coordination/department-directives/{directive_id}/acceptance" in paths
assert "/api/v1/coordination/department-directives/{directive_id}/revision-request" in paths
assert "/api/v1/tasks/department-directives/{directive_id}/acknowledgement" in paths
assert "/api/v1/tasks/department-directives/{directive_id}/submission" in paths
assert "/api/v1/tasks/department-directives/{directive_id}/acceptance" in paths
assert "/api/v1/tasks/department-directives/{directive_id}/revision-request" in paths
assert openapi["paths"]["/api/v1/coordination/alerts/{alert_id}/plans"]["post"].get(
    "deprecated"
) is not True
assert openapi["paths"]["/api/coordination/alerts/{alert_id}/apply"]["post"].get(
    "deprecated"
) is True
assert openapi["paths"]["/api/v1/coordination/department-directives/{directive_id}/acknowledgement"][
    "patch"
].get("deprecated") is not True
assert openapi["paths"]["/api/coordination/department-directives/{directive_id}/acknowledge"][
    "post"
].get("deprecated") is True
assert openapi["paths"]["/api/v1/tasks/department-directives/{directive_id}/acknowledgement"][
    "patch"
].get("deprecated") is not True
assert openapi["paths"]["/api/tasks/department-directives/{directive_id}/acknowledge"][
    "post"
].get("deprecated") is True
assert openapi["paths"]["/api/v1/alerts/{alert_id}"]["patch"].get("deprecated") is not True
assert openapi["paths"]["/api/alerts/{alert_id}/resolve"]["patch"].get("deprecated") is True
assert openapi["paths"]["/api/v1/overload/scans"]["post"].get("deprecated") is not True
assert openapi["paths"]["/api/overload/scan"]["post"].get("deprecated") is True
assert "/api/manager-evaluations" not in paths
assert "/api/ai/chat/stream" in paths
me_operation = openapi["paths"]["/api/v1/auth/me"]["get"]
assert me_operation["security"] == [{"CookieAuth": []}, {"BearerAuth": []}]
department_create = openapi["paths"]["/api/v1/departments"]["post"]
assert any(
    parameter.get("name") == "Idempotency-Key"
    for parameter in department_create.get("parameters", [])
)
assert department_create["responses"]["429"]["content"]["application/json"]["schema"]["$ref"] == (
    "#/components/schemas/V1ApiError"
)
assert openapi["paths"]["/api/departments"]["get"]["deprecated"] is True
assert openapi["paths"]["/api/v1/departments"]["get"].get("deprecated") is not True
public_paths = {
    "/api/health",
    "/api/v1/health",
    "/api/auth/login",
    "/api/v1/auth/login",
    "/api/auth/logout",
    "/api/v1/auth/logout",
}
for route in app.routes:
    if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
        continue
    if route.path in public_paths:
        continue
    names = dependency_names(route.dependant)
    assert names & {"get_current_user", "get_department_scope", "role_dependency"}, (
        f"Route thiếu dependency xác thực/RBAC: {route.path} {sorted(route.methods or [])}"
    )
legacy_http_paths = [
    path for path in paths if path.startswith("/api/") and not path.startswith("/api/v1/")
]
explicit_v1_successors = {
    # The v1 weekly evaluation route is intentionally resource-shaped rather
    # than a mechanical /api -> /api/v1 prefix replacement.
    "/api/department-evaluations/weekly-review": (
        "/api/v1/department-evaluations/weekly-evaluations"
    ),
}
for legacy_path in legacy_http_paths:
    v1_path = explicit_v1_successors.get(
        legacy_path, legacy_path.replace("/api/", "/api/v1/", 1)
    )
    assert v1_path in paths, (legacy_path, v1_path)
deprecated_routes = {
    ("/api/performance/daily", "post"),
    ("/api/overload/scan", "post"),
}
for path, method in deprecated_routes:
    assert openapi["paths"][path][method].get("deprecated") is True
included_routes = [
    route
    for included_router in app.routes
    if hasattr(included_router, "original_router")
    for route in included_router.original_router.routes
]
websocket_paths = [
    route.path for route in included_routes if route.__class__.__name__ == "APIWebSocketRoute"
]
assert "/ws/realtime" in websocket_paths
print("Registered routes:", ", ".join(paths), "WebSocket:", ", ".join(websocket_paths))
