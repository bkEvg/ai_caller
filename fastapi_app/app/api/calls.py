import asyncio
from fastapi import APIRouter, Body, Query

from app.ari.ari_commands import AriClient, WSHandler
from app.ari.ari_config import (ARI_HOST, AUTH_HEADER, WEBSOCKET_HOST)
from app.schemas.ai_agent import CallDB, CallListDB, CallCreate, PhoneCreate
from app.crud.ai_agent import create_call, get_calls_by_phone_digits

calls_router = APIRouter()


@calls_router.post(
    '/', response_model=CallDB, response_model_exclude_none=True,
    summary='Позвонить', tags=['Звонок'],
    description="Отправить запрос на вызов номера Нейро Ассистентом.")
async def make_call(request: CallCreate):
    # Инициализация клиента и WebSocket обработчика
    ari_client = AriClient(ARI_HOST, AUTH_HEADER)
    ws_handler = WSHandler(WEBSOCKET_HOST, AUTH_HEADER, ari_client,
                           request.phone.digits)

    # Подключаемся и начинаем слушать события
    asyncio.create_task(ws_handler.connect())

    # Создаем в базе обьект звонка телефона
    call = await create_call(request)
    return call


@calls_router.get('/{digits}', response_model=CallListDB)
async def get_calls_by_phone(digits: str):
    calls = get_calls_by_phone_digits(digits)
    return calls