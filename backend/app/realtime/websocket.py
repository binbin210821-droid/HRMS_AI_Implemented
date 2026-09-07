from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.api.dependencies import get_user_repository, resolve_current_user
from app.models.user import CurrentUser
from app.realtime.connection_manager import realtime_manager
from app.repositories.user_repository import UserRepository

router = APIRouter(tags=["Realtime"])


@router.websocket("/ws/realtime")
async def realtime_websocket(
    websocket: WebSocket,
    repository: UserRepository = Depends(get_user_repository),
) -> None:
    token = websocket.query_params.get("token")
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
