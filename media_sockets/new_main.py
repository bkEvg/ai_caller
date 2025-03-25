import os
import json
import websocket
import base64
import threading
import asyncio
import logging

from src.utils import AudioSocketParser, AudioConverter
from src.constants import OPENAI_API_KEY, REALTIME_URL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

url = REALTIME_URL
headers = [
    "Authorization: Bearer " + OPENAI_API_KEY,
    "OpenAI-Beta: realtime=v1"
]


class AudioWebSocketClient:
    def __init__(self, reader, writer, loop):
        self.reader = reader  # TCP-соединение (телефония)
        self.writer = writer  # Отправка данных обратно в телефонию
        self.ws = None
        self.loop = loop  # Передаем event loop

    def on_open(self, ws):
        """Отправляем команду для активации аудио-сессии."""
        logger.info("Connected to OpenAI Realtime API.")

        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
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

        # Запускаем отправку аудио в отдельном потоке
        threading.Thread(target=self.send_audio, args=(ws,),
                         daemon=True).start()

    def send_audio(self, ws):
        """Читает аудиопоток из reader и отправляет в OpenAI WebSocket."""
        parser = AudioSocketParser()
        logger.debug("send_audio() запущен, ждем данные...")
        while True:
            try:
                logger.debug("Ожидание аудиоданных из reader...")
                future = asyncio.run_coroutine_threadsafe(
                    self.reader.read(1024), self.loop)
                data = future.result(timeout=50)  # Ожидаем результат

                if not data:
                    logger.warning(
                        "Получен пустой пакет от reader. Закрываем "
                        "send_audio()")
                    break

                parser.buffer.extend(data)
                packet_type, packet_length, payload = parser.parse_packet()

                if packet_type == 0x10:  # Аудиоданные
                    pcm8k = AudioConverter.alaw_to_pcm(payload)
                    pcm24k = self.resample_audio(pcm8k, 8000, 24000)
                    b64_audio = base64.b64encode(pcm24k).decode("utf-8")
                    logger.debug(
                        f"Отправляем {len(pcm24k)} байт аудио в WebSocket")
                    ws.send(json.dumps({"type": "input_audio_buffer.append",
                                        "audio": b64_audio}))

            except Exception as e:
                logger.error(f"Ошибка отправки аудио: {e}")
                break

    def resample_audio(self, pcm_in: bytes, sr_in: int, sr_out: int) -> bytes:
        """Ресэмплирует PCM16 аудио с sr_in в sr_out."""
        import numpy as np
        from scipy.signal import resample_poly
        from fractions import Fraction

        data_int16 = np.frombuffer(pcm_in, dtype=np.int16)
        data_float = data_int16.astype(np.float32)

        ratio = Fraction(sr_out, sr_in).limit_denominator(1000)
        up = ratio.numerator
        down = ratio.denominator

        data_resampled = resample_poly(data_float, up, down)
        return data_resampled.astype(np.int16).tobytes()

    def on_message(self, ws, message):
        """Получает аудио-ответ от OpenAI и отправляет его обратно в телефонию."""
        try:
            event = json.loads(message)
            event_type = event.get("type", "")

            if event_type == "response.audio.delta":
                audio_b64 = event.get("delta", "")
                if audio_b64:
                    pcm24k = base64.b64decode(audio_b64)
                    pcm8k = self.resample_audio(pcm24k, 24000, 8000)

                    frame_length = 160
                    for i in range(0, len(pcm8k), frame_length):
                        self.writer.write(AudioConverter.create_audio_packet(
                            pcm8k[i:i + frame_length]))
                        asyncio.run_coroutine_threadsafe(self.writer.drain(),
                                                         self.loop)

            elif event_type == "response.text.delta":
                logger.info(f"Text chunk: {event.get('delta')}")

            elif event_type == "response.done":
                logger.info("Response finished")

        except Exception as e:
            logger.error(f"Ошибка обработки ответа WebSocket: {e}")

    def on_close(self, ws, close_status_code, close_msg):
        logger.info(f"WebSocket закрыт: {close_status_code} - {close_msg}")

    def on_error(self, ws, error):
        logger.error(f"Ошибка WebSocket: {error}")

    def run(self):
        """Запускает WebSocket-клиент."""
        self.ws = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=self.on_open,
            on_message=self.on_message,
            on_close=self.on_close,
            on_error=self.on_error
        )
        self.ws.run_forever()


async def handle_audiosocket_connection(reader, writer):
    """
    Запускает WebSocket-клиент для OpenAI, передаёт аудиоданные и отправляет ответы обратно.
    """
    loop = asyncio.get_running_loop()
    client = AudioWebSocketClient(reader, writer, loop)
    client.run()


async def main():
    HOST = '0.0.0.0'
    PORT = 7575

    server = await asyncio.start_server(handle_audiosocket_connection, HOST,
                                        PORT)
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())