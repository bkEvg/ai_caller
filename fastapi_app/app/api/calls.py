import asyncio
from fastapi import APIRouter
from ..ari.ari_commands import AriClient, WSHandler

from ..ari.ari_config import (ARI_HOST, AUTH_HEADER, WEBSOCKET_HOST)

calls_router = APIRouter()


@calls_router.post('')
async def create_call():
    # Инициализация клиента и WebSocket обработчика
    ari_client = AriClient(ARI_HOST, AUTH_HEADER)
    ws_handler = WSHandler(WEBSOCKET_HOST, AUTH_HEADER, ari_client)

    # Подключаемся и начинаем слушать события
    asyncio.create_task(ws_handler.connect())

    # Отправляем ответ сразу, не ожидая завершения WebSocket
    return {"message": "Вызов пошел", "status": "started"}
