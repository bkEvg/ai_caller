import asyncio
from fastapi import APIRouter, Body

from app.ari.ari_commands import AriClient, WSHandler
from app.ari.ari_config import (ARI_HOST, AUTH_HEADER, WEBSOCKET_HOST)
from app.schemas.ai_agent import PhoneRequest, CallResponse, PhoneExamples
from app.crud.ai_agent import get_phone, create_call, create_phone

calls_router = APIRouter()


@calls_router.post('', response_model=CallResponse,
                   summary='Позвонить',
                   description=("Отправить запрос на вызов "
                                "номера Нейро Ассистентом."),
                   tags=['Звонок'])
async def make_call(
        phone_request: PhoneRequest = Body(
            ..., openapi_examples=PhoneExamples.get_openapi_examples()
        ),):
    # Инициализация клиента и WebSocket обработчика
    ari_client = AriClient(ARI_HOST, AUTH_HEADER)
    ws_handler = WSHandler(WEBSOCKET_HOST, AUTH_HEADER, ari_client,
                           phone_request.digits)

    # Подключаемся и начинаем слушать события
    asyncio.create_task(ws_handler.connect())

    # Создаем в базе обьекты звонка телефона
    phone = await get_phone(phone_request)
    if not phone:
        phone = await create_phone(phone_request)
    call = await create_call(
        phone, channel_id=ws_handler.client_channel_id
    )
    return call
