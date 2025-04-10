import json
import base64
import asyncio
import websockets
import logging

from src.utils import (AudioSocketParser, AudioSocketConsumer,
                       AudioTrasferService, AudioConverter)
from src.constants import (OPENAI_API_KEY, REALTIME_URL, HOST, PORT,
                           INPUT_FORMAT, OUTPUT_FORMAT)

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s [%(levelname)s] %(funcName)s"
            " at - %(lineno)d line: %(message)s"),
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

headers = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "OpenAI-Beta": "realtime=v1"
}


class AudioWebSocketClient:
    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer
        self.ws = None
        self.timer = 0

    async def send_initial_conversation_item(ws):
        """Send initial conversation item if AI talks first."""
        initial_conversation_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": ("Greet the user with 'Hello there! I am "
                                 "an AI voice assistant powered by Twilio "
                                 "and the OpenAI Realtime API. You can ask "
                                 "me for facts, jokes, or anything you can "
                                 "imagine. How can I help you?'")
                    }
                ]
            }
        }
        await ws.send(json.dumps(initial_conversation_item))
        await ws.send(json.dumps({"type": "response.create"}))

    async def on_open(self):
        """Отправляем команду для активации аудио-сессии."""
        logger.info("WebSocket подключен!")

        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "input_audio_format": INPUT_FORMAT,
                "output_audio_format": OUTPUT_FORMAT,
                "voice": "shimmer",
                "instructions": "Отвечай четко и дружелюбно на русском.",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.3,
                    "silence_duration_ms": 500,
                    "prefix_padding_ms": 500,
                    "create_response": True,
                    "interrupt_response": True
                }
            }
        }

        await self.ws.send(json.dumps(session_update))
        logger.info("Отправлен запрос session.update")

        # Запускаем отправку аудио
        self.listener_task = asyncio.create_task(self.send_audio())

        # Отправляем начальный элемент разговора
        # await self.send_initial_conversation_item(self.ws)

    async def send_audio(self):
        """Читает аудиопоток из reader и отправляет в WebSocket."""
        parser = AudioSocketParser()
        logger.info("send_audio() запущен, ждем данные...")

        while True:
            try:
                data = await self.reader.read(1024)

                if not data:
                    logger.warning(
                        "Получен пустой пакет от reader. "
                        "Ожидаем в send_audio()")
                    continue  # Если аудио закончилось, выходим из цикла

                # Добавляем в парсер
                parser.buffer.extend(data)
                packet_type, packet_length, payload = parser.parse_packet()

                if packet_type == 0x10:  # Аудиоданные
                    b64_audio = base64.b64encode(payload).decode("utf-8")
                    await self.ws.send(json.dumps(
                        {"type": "input_audio_buffer.append",
                         "audio": b64_audio}))

                else:
                    logger.warning(f"Пропущен пакет типа {packet_type}")

            except Exception as e:
                logger.error(f"Ошибка в send_audio(): {e}")
                break

    async def on_message(self, message, background_consume_service):
        """
        Получает аудио-ответ от OpenAI и отправляет его обратно в
        телефонию.
        """
        try:
            event = json.loads(message)
            event_type = event.get("type", "")

            if event_type == "response.audio.delta":
                audio_b64 = event.get("delta", "")
                if audio_b64:
                    pcm24k = base64.b64decode(audio_b64)
                    pcm8k = AudioConverter.resample_audio(pcm24k, 24000, 8000)
                    background_consume_service.add_data(pcm8k)

            elif event_type == "response.text.delta":
                logger.info(f"Text chunk: {event.get('delta')}")

            elif event_type == "response.done":
                logger.info("Response finished")

        except Exception as e:
            logger.error(f"Ошибка обработки ответа WebSocket: {e}")

    async def run(self):
        """Запускает WebSocket-клиент."""
        logger.debug('run() started')
        async with websockets.connect(REALTIME_URL, additional_headers=headers,
                                      ping_interval=None) as ws:
            self.ws = ws
            await self.on_open()

            # Слушаем сообщения от WebSocket
            socket_consumer = AudioSocketConsumer(self.writer)
            background_consume_service = AudioTrasferService(
                socket_consumer)
            async for message in ws:
                await self.on_message(message, background_consume_service)


async def handle_audiosocket_connection(reader, writer):
    """
    Запускает WebSocket-клиент для OpenAI, передаёт аудиоданные и
    отправляет ответы обратно.
    """
    logger.debug('handle_audiosocket_connection() started')
    client = AudioWebSocketClient(reader, writer)
    await client.run()


async def main():
    server = await asyncio.start_server(
        handle_audiosocket_connection, HOST, PORT)
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
