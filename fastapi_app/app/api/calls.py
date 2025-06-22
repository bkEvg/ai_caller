import asyncio
from fastapi import APIRouter
import uuid

from app.ari.ari_commands import AriClient, WSHandler
from app.ari.ari_config import (ARI_HOST, AUTH_HEADER, WEBSOCKET_HOST)
from app.schemas.ai_agent import CallDB, PhoneCreate
from app.crud.ai_agent import get_calls_by_phone_digits

calls_router = APIRouter()


@calls_router.post(
    '/',
    summary='Позвонить', tags=['Звонок'],
    description="Отправить запрос на вызов номера Нейро Ассистентом.")
async def make_call(request: PhoneCreate):
    # Инициализация клиента и WebSocket обработчика
    call_uuid = str(uuid.uuid4())
    ari_client = AriClient(ARI_HOST, AUTH_HEADER)
    ws_handler = WSHandler(WEBSOCKET_HOST, AUTH_HEADER, ari_client,
                           request.digits, call_uuid)

    # Подключаемся и начинаем слушать события
    asyncio.create_task(ws_handler.connect())
    return 'created'


# @calls_router.post(
#     '/clean',
#     tags=['Звонок'])
# async def make_call(request: PhoneCreate):
#     # Инициализация клиента и WebSocket обработчика
#     call_uuid = "f47ac10b-58cc-4372-a567-0e02b2c3d479"
#     ari_client = AriClient(ARI_HOST, AUTH_HEADER)
#     ws_handler = WSHandler(WEBSOCKET_HOST, AUTH_HEADER, ari_client,
#                            request.digits, call_uuid)

#     # Подключаемся и начинаем слушать события
#     asyncio.create_task(ws_handler.connect())
#     return 'created'


@calls_router.get('/{digits}', response_model=list[CallDB],
                  summary='Получить все звонки по телефону',
                  tags=['Телефон'])
async def get_calls_by_phone(digits: str):
    calls = await get_calls_by_phone_digits(digits)
    return calls