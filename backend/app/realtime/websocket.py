from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.api.dependencies import get_user_repository, resolve_current_user
from app.core.config import get_settings
from app.infrastructure.rate_limit.middleware import _runtime_components_from_app
from app.models.user import CurrentUser
from app.realtime.connection_manager import realtime_manager
from app.repositories.user_repository import UserRepository

router = APIRouter(tags=["Realtime"])


@router.websocket("/ws/realtime")
async def realtime_websocket(
    websocket: WebSocket,
    repository: UserRepository = Depends(get_user_repository),
) -> None:
    settings = getattr(websocket.app.state, "settings", None)
    if settings is None:
        settings = get_settings()
    if settings.rate_limit_enabled:
        limiter, policy, keys = _runtime_components_from_app(websocket.app)
        rule = policy.rule_for_group("websocket_handshake")
        key = keys.build_for_group(websocket, rule.group)
        if isinstance(key, tuple):
            key = key[0]
        try:
            decision = await limiter.check(key, rule.limit, rule.window_seconds)
        except Exception:
            await websocket.close(
                code=1013,
                reason="Quá nhiều kết nối, vui lòng thử lại sau",
            )
            return
        if not decision.allowed:
            await websocket.close(
                code=1013,
                reason="Quá nhiều kết nối, vui lòng thử lại sau",
            )
            return
    cookie_token = websocket.cookies.get(settings.auth_access_cookie_name)
    query_token = websocket.query_params.get("token")
    if query_token and not settings.legacy_ws_query_token_enabled:
        query_token = None
    if cookie_token and query_token and cookie_token != query_token:
        await websocket.close(code=1008, reason="Thông tin xác thực không khớp")
        return
    token = cookie_token or query_token
    if not token:
        await websocket.close(code=1008, reason="Thiếu token xác thực")
        return

    try:
        user: CurrentUser = await resolve_current_user(token, repository)
    except HTTPException:
        await websocket.close(code=1008, reason="Token không hợp lệ")
        return

    await realtime_manager.connect(websocket, user)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime_manager.disconnect(websocket)
