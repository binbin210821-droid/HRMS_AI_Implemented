import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app

openapi = app.openapi()
paths = list(openapi["paths"])
assert "/api/health" in paths
assert "/api/auth/login" in paths
assert "/api/auth/me" in paths
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
assert "/api/manager-evaluations" not in paths
assert "/api/ai/chat/stream" in paths
deprecated_routes = {
    ("/api/coordination/alerts/{alert_id}/direct", "post"),
    ("/api/coordination/alerts/{alert_id}/directive-targets", "get"),
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
