from typing import Optional
import asyncio

import httpx
import websockets
import json
import logging

from .ari_config import (ARI_HOST, SIP_ENDPOINT, STASIS_APP_NAME, EXTERNAL_HOST)

logger = logging.getLogger(__name__)

class AriClient:
    """Клиент для работы с ARI."""

    def __init__(self, base_url: str, headers: dict):
        self.base_url = base_url
        self.headers = headers
        self.client = httpx.AsyncClient()

    def _normalize_response(self, response) -> dict:
        """Нормализуем ответ от ARI и проверяем статус."""
        status = response.status_code
        if not response:
            return {}
        if status != 200 and not 204:
            raise RuntimeError(f"Ошибка от ARI: {response.text}")
        return response.json() if response.text else {}

    async def _send_request(self, url: str, method: str, data: Optional[
            dict] = None) -> dict:
        """Отправляем асинхронный запрос."""
        if method.lower() == 'post':
            response = await self.client.post(
                url, json=data, headers=self.headers)
        elif method.lower() == 'delete':
            response = await self.client.delete(url)
        else:
            raise ValueError('Unsupported method')
        return self._normalize_response(response)

    async def create_channel(self, endpoint: str) -> dict:
        """Создать канал."""
        url = f'{self.base_url}/channels/create'
        data = {
            "endpoint": endpoint,
            "app": STASIS_APP_NAME,
            "timeout": 30
        }
        return await self._send_request(url, 'POST', data)

    async def dial_channel(self, channel_id: str) -> None:
        """Подключание канала."""
        url = f"{self.base_url}/channels/{channel_id}/dial"
        await self._send_request(url, "POST")

    async def play_audio(self, channel_id: str) -> None:
        """Воспроизвести звук."""
        url = f"{self.base_url}/channels/{channel_id}/play"
        data = {
            "media": "sound:hello-world"  # http://217.114.3.34/audio-2.alaw
        }
        await self._send_request(url, 'POST', data)

    async def record_call(
            self, channel_id, filename="client_call_recording",
            format="wav", beep=True, max_duration_seconds=0,
            max_silence_seconds=0, if_exists="overwrite") -> dict:
        """Запись звонка с динамическими параметрами."""
        url = f"{ARI_HOST}/channels/{channel_id}/record"

        data = {
            "format": format,  # формат записи (например, wav или mp3)
            "name": filename,  # имя файла записи
            "beep": beep,  # флаг для воспроизведения сигнала перед записью
            "maxDurationSeconds": max_duration_seconds,
            # максимальная продолжительность записи
            "maxSilenceSeconds": max_silence_seconds,
            # максимальное время тишины, после которого запись завершится
            "ifExists": if_exists
            # что делать, если файл существует (overwrite или append)
        }
        await self._send_request(url, "POST", data)

    async def hangup_call(self, channel_id: int) -> None:
        """Завершение звонка."""
        url = f"{self.base_url}/channels/{channel_id}"
        await self._send_request(url, "DELETE")

    async def create_bridge(self) -> str:
        """Создает бридж, и возвращает его id."""
        url = f"{self.base_url}/bridges"
        response = await self._send_request(url, "POST", {"type": "mixing"})
        return response['id']

    async def add_channel_to_bridge(self, bridge_id: str,
                                    channel_id: str) -> None:
        """Добавить канал в бридж."""
        url = f"{ARI_HOST}/bridges/{bridge_id}/addChannel"
        data = {"channel": channel_id}
        await self._send_request(url, "POST", data)

    async def record_bridge(self, bridge_id: str, filename: str) -> None:
        """Записать бридж."""
        url = f"{ARI_HOST}/bridges/{bridge_id}/record"
        data = {
            "name": filename,
            "format": "gsm",
            "ifExists": "overwrite",
            "beep": True
        }
        await self._send_request(url, "POST", data)

    async def create_external_media(self):
        url = f"{ARI_HOST}/channels/externalMedia"
        data = {
            "app": STASIS_APP_NAME,
            "external_host": EXTERNAL_HOST,
            "encapsulation": "audiosocket",
            "transport": "tcp",
            "format": "s16lin",
            "data": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
        }
        return await self._send_request(url, 'POST', data)

    async def create_snoop_on_channel(self, channel_id) -> dict:
        url = f"{ARI_HOST}/channels/{channel_id}/snoop"
        data = {
            "spy": "both",
            "whisper": "both",
            "app": STASIS_APP_NAME
        }
        return await self._send_request(url, 'POST', data)


class WSHandler:
    """Обработчик WebSocket событий."""

    def __init__(self, ws_host: str, headers: dict, ari_client: AriClient):
        self.ws_host = ws_host
        self.headers = headers
        self.ari_client = ari_client
        self.current_bridge_id = None
        self.client_channel_id = None
        self.snoop_channel_id = None

    async def handle_events(self, websocket):
        """Обрабатываем события."""
        while True:
            message = await websocket.recv()
            event = json.loads(message)
            logger.error(message)
            if event['type'] == 'StasisStart':
                channel_id = event['channel']['id']
                await asyncio.sleep(10)
                await self.ari_client.dial_channel(channel_id)

            if event['type'] == 'Dial' and event['dialstatus'] == 'ANSWER':
                await self.ari_client.play_audio(self.client_channel_id)

    async def connect(self):
        """Подключаемся по WebSocket и обрабатываем события."""
        async with websockets.connect(
                self.ws_host, additional_headers=self.headers) as websocket:
            logger.error('Connected to ARI with app %s', STASIS_APP_NAME)

            self.current_bridge_id = await self.ari_client.create_bridge()

            logger.error(f'BRIDGE: {self.current_bridge_id}')

            # Создаем канал для вызова, и цепляем к нему прослушку
            client = await self.ari_client.create_channel(SIP_ENDPOINT)
            self.client_channel_id = client['id']
            logger.error(f'CLIENT_CHANNEL_ID: {self.client_channel_id}')
            # snoop_channel = await self.ari_client.create_snoop_on_channel(
            #     client['id'])
            # self.snoop_channel_id = snoop_channel['id']
            # logger.error(f"SOOP: {self.snoop_channel_id}")

            await self.ari_client.add_channel_to_bridge(
                self.current_bridge_id, self.client_channel_id)

            # Создаем передачу потока во внешний ресурс
            external_media = await self.ari_client.create_external_media()
            await self.ari_client.add_channel_to_bridge(
                self.current_bridge_id, external_media['id'])

            await self.handle_events(websocket)
