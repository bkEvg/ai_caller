import asyncio
from fastapi import APIRouter
from pydantic import BaseModel

from ..ari.ari_commands import AriClient, WSHandler
from ..ari.ari_config import (ARI_HOST, AUTH_HEADER, WEBSOCKET_HOST)

calls_router = APIRouter()


class CallRequest(BaseModel):
    phone: str


@calls_router.post('')
async def create_call(request: CallRequest):
    # Инициализация клиента и WebSocket обработчика
    ari_client = AriClient(ARI_HOST, AUTH_HEADER)
    ws_handler = WSHandler(WEBSOCKET_HOST, AUTH_HEADER, ari_client,
                           request.phone)

    # Подключаемся и начинаем слушать события
    asyncio.create_task(ws_handler.connect())

    # Отправляем ответ сразу, не ожидая завершения WebSocket
    return {"message": "Вызов пошел", "status": "started"}
