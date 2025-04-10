import os
import json
import base64
import threading
import websocket
import logging
import asyncio
from time import sleep

from src.utils import (AudioSocketParser, AudioSocketConsumer,
                       AudioTrasferService, AudioConverter)
from src.constants import (OPENAI_API_KEY, REALTIME_URL, HOST, PORT,
                           INPUT_FORMAT, OUTPUT_FORMAT)

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s [%(levelname)s] %(funcName)s at - %(lineno)d line: %(message)s"),
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

    def on_open(self, ws):
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

        ws.send(json.dumps(session_update))
        logger.info("Отправлен запрос session.update")

        # Запускаем отправку аудио в отдельном потоке
        threading.Thread(target=self.send_audio, args=(ws,), daemon=True).start()

    def on_message(self, ws, message):
        """
        Получает аудио-ответ от OpenAI и отправляет его обратно в телефонию.
        """
        try:
            event = json.loads(message)
            event_type = event.get("type", "")

            if event_type == "response.audio.delta":
                audio_b64 = event.get("delta", "")
                if audio_b64:
                    pcm24k = base64.b64decode(audio_b64)
                    pcm8k = AudioConverter.resample_audio(pcm24k, 24000, 8000)
                    min_data = 160
                    pause = 0.02
                    for chunk in range(0, len(pcm8k), min_data):
                        chunk_data = pcm8k[chunk:chunk + min_data]
                        if chunk_data:
                            self.writer.write(chunk_data)
                            self.writer.drain()

            elif event_type == "response.text.delta":
                logger.info(f"Text chunk: {event.get('delta')}")

            elif event_type == "response.done":
                logger.info("Response finished")

        except Exception as e:
            logger.error(f"Ошибка обработки ответа WebSocket: {e}")

    def send_audio(self, ws):
        """Читает аудиопоток из reader и отправляет в WebSocket."""
        parser = AudioSocketParser()
        logger.info("send_audio() запущен, ждем данные...")

        while True:
            try:
                data = self.reader.read(1024)

                if not data:
                    logger.warning("Получен пустой пакет от reader. Ожидаем в send_audio()")
                    continue  # Если аудио закончилось, выходим из цикла

                # Добавляем в парсер
                parser.buffer.extend(data)
                packet_type, packet_length, payload = parser.parse_packet()

                if packet_type == 0x10:  # Аудиоданные
                    b64_audio = base64.b64encode(payload).decode("utf-8")
                    ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": b64_audio}))
                else:
                    logger.warning(f"Пропущен пакет типа {packet_type}")

            except Exception as e:
                logger.error(f"Ошибка в send_audio(): {e}")
                break

    def run(self):
        """Запускает WebSocket-клиент."""
        ws_app = websocket.WebSocketApp(
            REALTIME_URL,
            header=headers,
            on_open=self.on_open,
            on_message=self.on_message
        )

        # Запускаем WebSocket в отдельном потоке, чтобы не блокировать основной поток
        ws_thread = threading.Thread(target=ws_app.run_forever, daemon=True)
        ws_thread.start()

        # Запускаем цикл ожидания соединения и сообщений
        ws_thread.join()


def handle_audiosocket_connection(reader, writer):
    """Запускает WebSocket-клиент для OpenAI, передает аудиоданные и отправляет ответы обратно."""
    logger.debug('handle_audiosocket_connection() started')
    client = AudioWebSocketClient(reader, writer)
    client.run()


async def main():
    server = await asyncio.start_server(
        handle_audiosocket_connection, HOST, PORT)
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
