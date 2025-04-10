import json
import base64
import asyncio
import websockets
import logging

from src.utils import AudioSocketParser, AudioConverter
from src.constants import OPENAI_API_KEY, REALTIME_URL, HOST, PORT

logging.basicConfig(
    level=logging.DEBUG,
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

    async def on_open(self):
        """Отправляем команду для активации аудио-сессии."""
        logger.info("WebSocket подключен!")

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

        await self.ws.send(json.dumps(session_update))
        logger.info("Отправлен запрос session.update")

        # Запускаем отправку аудио
        self.listener_task = asyncio.create_task(self.send_audio())

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
                    pcm8k = AudioConverter.alaw_to_pcm(payload)
                    pcm24k = self.resample_audio(pcm8k, 8000, 24000)
                    b64_audio = base64.b64encode(pcm24k).decode("utf-8")

                    logger.info(
                        f"Отправляем {len(pcm24k)} байт аудио в WebSocket")
                    await self.ws.send(json.dumps(
                        {"type": "input_audio_buffer.append",
                         "audio": b64_audio}))

                else:
                    logger.warning(f"Пропущен пакет типа {packet_type}")

            except Exception as e:
                logger.error(f"Ошибка в send_audio(): {e}")
                break

    @staticmethod
    def resample_audio(pcm_in: bytes, sr_in: int, sr_out: int) -> bytes:
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

    async def on_message(self, message):
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
                    pcm8k = self.resample_audio(pcm24k, 24000, 8000)

                    # 20 мс для 8 кГц (16 бит на семпл, 160 семплов на канал)
                    frame_length = 320
                    frame_duration_sec = 0.02
                    for i in range(0, len(pcm8k), frame_length):
                        self.writer.write(AudioConverter.create_audio_packet(
                            pcm8k[i:i + frame_length]))
                        await self.writer.drain()
                        await asyncio.sleep(frame_duration_sec)
                        self.timer += frame_duration_sec
                        logger.info(f"Итого поспали: {self.timer}")

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
            async for message in ws:
                await self.on_message(message)


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
