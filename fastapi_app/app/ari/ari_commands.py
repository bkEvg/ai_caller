from typing import Optional
import asyncio

import httpx
import websockets
import json
import logging

from .ari_config import (ARI_HOST, STASIS_APP_NAME, EXTERNAL_HOST, SIP_HOST, ARI_TIMEOUT)
from app.crud.ai_agent import create_call, append_status_to_call
from app.schemas.ai_agent import (CallCreate, PhoneCreate, CallStatusDB,
                                  CallStatuses)

logger = logging.getLogger(__name__)


class AriClient:
    """Клиент для работы с ARI."""

    def __init__(self, base_url: str, headers: dict):
        self.base_url = base_url
        self.headers = headers
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(ARI_TIMEOUT))

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

    async def create_external_media(self, uuid: str):
        url = f"{ARI_HOST}/channels/externalMedia"
        data = {
            "app": STASIS_APP_NAME,
            "external_host": EXTERNAL_HOST,
            "encapsulation": "audiosocket",
            "transport": "tcp",
            "format": "alaw",
            "data": uuid
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

    def __init__(self, ws_host: str, headers: dict, ari_client: AriClient,
                 phone: str, uuid: str):
        self.ws_host = ws_host
        self.headers = headers
        self.ari_client = ari_client
        self.phone = phone
        self.uuid = uuid
        self.call = None
        self.sip_endpoint = f'SIP/{self.phone}@{SIP_HOST}'
        self.current_bridge_id: str = None
        self.current_external_id: str = None
        self.client_channel_id: str = None

    def parse_qos_data(value: str) -> dict:
        """Парсит строку формата key=value;key=value в словарь."""
        return dict(item.split('=') for item in value.strip(';').split(';') if '=' in item)

    async def handle_connection_info(self, event_type: str, event: dict) -> None:
        """Обрабатываем информацию приходящую о соединении."""
        logger.error(event)
        event_var = event.get('variable')
        value = event.get('value', '')
        channel = event.get('channel', {})
        channel_name = channel.get("name", "unknown")

        def log_qos_info(title: str, parsed: dict):
            logger.info(f"\n📡 {title} для канала {channel_name}")
            for k, v in parsed.items():
                logger.info(f"{k}: {v}")

        if event_var == 'STASISSTATUS':
            logger.info(f"🌀 Статус подключения к Stasis: {value or 'EMPTY'} для канала {channel_name}")

        elif event_var == 'BRIDGEPEER':
            logger.info(f"🔗 Канал {channel_name} соединён с: {value or 'пусто'}")

        elif event_var == 'BRIDGEPVTCALLID':
            logger.info(f"🔐 Private Call ID в бридже: {value}")

        elif event_var in ['RTPAUDIOQOS', 'RTPAUDIOQOSBRIDGED']:
            title = "📊 RTP QoS (основной канал)" if event_var == 'RTPAUDIOQOS' else "📊 RTP QoS (bridged канал)"
            data = self.parse_qos_data(value)
            log_qos_info(title, {
                "ssrc": data.get("ssrc"),
                "themssrc": data.get("themssrc"),
                "lp (local loss)": data.get("lp"),
                "rxjitter": data.get("rxjitter"),
                "rxcount": data.get("rxcount"),
                "txjitter": data.get("txjitter"),
                "txcount": data.get("txcount"),
                "rlp (remote loss)": data.get("rlp"),
                "rtt (ping round-trip)": data.get("rtt"),
                "rxmes (media delay recv)": data.get("rxmes"),
                "txmes (media delay send)": data.get("txmes"),
            })

        elif event_var in ['RTPAUDIOQOSJITTER', 'RTPAUDIOQOSJITTERBRIDGED']:
            title = "🎯 Jitter статистика (основной)" if event_var == 'RTPAUDIOQOSJITTER' else "🎯 Jitter статистика (bridged)"
            data = self.parse_qos_data(value)
            log_qos_info(title, {
                "minrxjitter": data.get("minrxjitter"),
                "maxrxjitter": data.get("maxrxjitter"),
                "avgrxjitter": data.get("avgrxjitter"),
                "stdevrxjitter": data.get("stdevrxjitter"),
                "mintxjitter": data.get("mintxjitter"),
                "maxtxjitter": data.get("maxtxjitter"),
                "avgtxjitter": data.get("avgtxjitter"),
                "stdevtxjitter": data.get("stdevtxjitter"),
            })

        elif event_var in ['RTPAUDIOQOSLOSS', 'RTPAUDIOQOSLOSSBRIDGED']:
            title = "❌ Потери пакетов (основной)" if event_var == 'RTPAUDIOQOSLOSS' else "❌ Потери пакетов (bridged)"
            data = self.parse_qos_data(value)
            log_qos_info(title, {
                "minrxlost": data.get("minrxlost"),
                "maxrxlost": data.get("maxrxlost"),
                "avgrxlost": data.get("avgrxlost"),
                "stdevrxlost": data.get("stdevrxlost"),
                "mintxlost": data.get("mintxlost"),
                "maxtxlost": data.get("maxtxlost"),
                "avgtxlost": data.get("avgtxlost"),
                "stdevtxlost": data.get("stdevtxlost"),
            })

        elif event_var in ['RTPAUDIOQOSRTT', 'RTPAUDIOQOSRTTBRIDGED']:
            title = "⏱ RTT статистика (основной)" if event_var == 'RTPAUDIOQOSRTT' else "⏱ RTT статистика (bridged)"
            data = self.parse_qos_data(value)
            log_qos_info(title, {
                "minrtt": data.get("minrtt"),
                "maxrtt": data.get("maxrtt"),
                "avgrtt": data.get("avgrtt"),
                "stdevrtt": data.get("stdevrtt"),
            })

        elif event_var in ['RTPAUDIOQOSMES', 'RTPAUDIOQOSMESBRIDGED']:
            title = "📐 Media Delay (основной)" if event_var == 'RTPAUDIOQOSMES' else "📐 Media Delay (bridged)"
            data = self.parse_qos_data(value)
            log_qos_info(title, {
                "minrxmes": data.get("minrxmes"),
                "maxrxmes": data.get("maxrxmes"),
                "avgrxmes": data.get("avgrxmes"),
                "stdevrxmes": data.get("stdevrxmes"),
                "mintxmes": data.get("mintxmes"),
                "maxtxmes": data.get("maxtxmes"),
                "avgtxmes": data.get("avgtxmes"),
                "stdevtxmes": data.get("stdevtxmes"),
            })

        else:
            logger.info(f"🔍 Необработанная переменная: {event_var} = {value}")

    async def handle_client_channel_events(
            self, event_type: str, event: dict) -> None:
        """Обрабатываем события относящиеся только к Клиентскому каналу."""

        # Client channel info
        channel_info: dict = event.get('channel', {})

        # Mark True if event is related to client_channel
        client_channel_event = channel_info.get('id') == self.client_channel_id

        # Mark True if client_channel has answered call
        client_channel_answer = (
            event.get('dialstatus') == 'ANSWER'
            and event.get('peer', {}).get('id') == self.client_channel_id
        )
        logger.info(
            f"ОТВЕТИЛИИИИИИ???? {client_channel_answer} а вот почему "
            f"peer.id, status = {event.get('peer', {}).get('id'), event.get('dialstatus')}"
        )
        if event_type == 'StasisStart' and client_channel_event:
            logger.error('Приложение получило доступ к управлению')
            await append_status_to_call(
                self.client_channel_id,
                [CallStatusDB(status_str=CallStatuses.STASIS_START)])
            await self.ari_client.dial_channel(self.client_channel_id)

        elif event_type == 'Dial' and client_channel_answer:
            logger.error('Абонент ответил')
            await self.ari_client.add_channel_to_bridge(
                self.current_bridge_id, self.current_external_id)
            await append_status_to_call(
                self.client_channel_id,
                [CallStatusDB(status_str=CallStatuses.ANSWERED)])

        elif event_type == 'ChannelHangupRequest' and client_channel_event:
            logger.error('Абонент сбросил')

    async def handle_events(self, websocket: websockets.ClientConnection):
        """Обрабатываем websocket события."""
        # while True:
        # message = await websocket.recv()
        async for message in websocket:
            logger.info(message)
            event = json.loads(message)
            event_type = event['type']
            await self.handle_client_channel_events(event_type, event)
            if event_type == 'ChannelVarset':
                # Если событие с переменной канала - это инфа о соединении
                await self.handle_connection_info(event_type, event)

    async def connect(self):
        """Подключаемся по WebSocket и обрабатываем события."""
        async with websockets.connect(
                self.ws_host, additional_headers=self.headers) as websocket:
            logger.info('Connected to ARI with app %s', STASIS_APP_NAME)

            self.current_bridge_id = await self.ari_client.create_bridge()

            logger.info(f'BRIDGE: {self.current_bridge_id}')

            # Создаем канал для вызова
            logger.error(f'SIP_ENDPOINT: {self.sip_endpoint}')
            client = await self.ari_client.create_channel(self.sip_endpoint)
            self.client_channel_id = client['id']

            # Создаем в базе обьект звонка телефона
            phone_data = PhoneCreate(digits=self.phone)
            call_data = CallCreate(
                channel_id=self.client_channel_id, phone=phone_data,
                uuid=self.uuid,
                statuses=[CallStatusDB(status_str=CallStatuses.CREATED)]
            )
            self.call = await create_call(call_data)

            logger.error(f'CLIENT_CHANNEL_ID: {self.client_channel_id}')
            logger.error(f'BRIDGE_ID: {self.current_bridge_id}')

            external_media = await self.ari_client.create_external_media(
                self.uuid)

            logger.error(f'EXTERNAL_MEDIA_ID: {external_media}')
            self.current_external_id = external_media['id']
            # Создаем передачу потока во внешний ресурс
            await self.ari_client.add_channel_to_bridge(
                self.current_bridge_id, self.client_channel_id)

            await self.handle_events(websocket)
