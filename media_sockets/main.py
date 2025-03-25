import asyncio
import base64
import logging
import numpy as np
from scipy.signal import resample_poly
from fractions import Fraction
import json
import websockets

from src.utils import AudioSocketParser, AudioConverter
from src.constants import OPENAI_API_KEY, REALTIME_URL

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s [%(levelname)s] %(funcName)s"
            " at - %(lineno)d line: %(message)s"),
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def resample_audio(pcm_in: bytes, sr_in: int, sr_out: int) -> bytes:
    """
    Ресэмплирует сырые байты PCM16 (моно) с частоты sr_in (Hz)
    на частоту sr_out (Hz), возвращая байты PCM16 (моно).
    """
    # Превращаем сырые байты int16 -> float32, чтобы scipy могло ресэмплировать
    data_int16 = np.frombuffer(pcm_in, dtype=np.int16)
    data_float = data_int16.astype(np.float32)

    # Рассчитываем рациональное отношение up/down
    # Пример: 16000 / 8000 = 2/1
    # или 44100 / 16000 ~ 441/160
    ratio = Fraction(sr_out, sr_in).limit_denominator(1000)
    up = ratio.numerator
    down = ratio.denominator

    # Выполняем ресэмплинг
    # resample_poly(data, up, down) изменяет частоту в up/down раз
    data_resampled = resample_poly(data_float, up, down)

    # Обратно приводим к int16
    data_int16_out = data_resampled.astype(np.int16)
    return data_int16_out.tobytes()


async def realtime_listener(websocket, writer):
    """
    Задача, которая получает события от Realtime API
    и отправляет аудио обратно в телефонию.
    """
    while True:
        # Ждём следующего server->client сообщения от Realtime API
        msg = await websocket.recv()
        event = json.loads(msg)
        event_type = event.get("type", "")
        logger.info(f"Получено сообщение от WebSocket {event_type} ")

        # Модель присылает аудио частями через response.audio.delta
        if event_type == "response.audio.delta":
            audio_b64 = event.get("delta", "")
            if audio_b64:
                pcm24k = base64.b64decode(audio_b64)
                pcm8k = resample_audio(pcm24k, 24000, 8000)
                if writer.is_closing():
                    logger.warning("Writer закрывается, прерываем отправку")
                    return
                frame_length = 160
                for i in range(0, len(pcm8k), frame_length):
                    writer.write(AudioConverter.create_audio_packet(
                        pcm8k[i:i+frame_length]
                    ))

                    await writer.drain()
                    await asyncio.sleep(0.01)

        elif event_type == "response.text.delta":
            # Если нужен текст - обрабатываем.
            text_chunk = event.get("delta", "")
            logger.info("Text chunk from model:", text_chunk)
        elif event_type == "response.audio_transcript.delta":
            logger.info(f"Text trascription: {event.get('delta')}")

        elif event_type == "response.done":
            logger.info("Response finished:", event)

        else:
            # Для отладки
            # logger.info("Other event:", event)
            pass


async def handle_audiosocket_connection(reader, writer):
    """
    Обработка одного входящего TCP-соединения AudioSocket.
    Здесь читаем входящие 8k-пакеты и отправляем их в Realtime API.
    Возвращаем управление, когда клиент (телефония) закрыла соединение.
    """
    # Устанавливаем WebSocket-соединение с Realtime API
    async with websockets.connect(
        REALTIME_URL,
        additional_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as ws:
        logger.info("Connected to Realtime API.")

        # Настраиваем сессию: audio input/output, PCM16
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",

                # Меняем голос
                # 'alloy', 'ash', 'ballad', 'coral', 'echo', 'sage',
                # 'shimmer', and 'verse'
                "voice": "shimmer",

                # Общий стиль (тон голоса, запреты на слова,
                # "характер" ассистента):
                "instructions": (
                    "Ты дружелюбный, мягко говорящий ассистент. "
                    "Говори с небольшой улыбкой, делай лёгкие паузы. "
                    "Избегай резких интонаций."
                    "Отвечай всегда строго на русском языке"
                ),
                # Можно настроить VAD, температуру и т.п.
                "turn_detection": {
                    "type": "server_vad",
                    # Порог чувствительности(0.0...1.0)
                    "threshold": 0.3,
                    # Сколько миллисекунд тишины считать концом речи
                    "silence_duration_ms": 500,
                    # Сколько миллисекунд звука сохранять "до" VAD -
                    # срабатывания
                    "prefix_padding_ms": 500,
                    "create_response": True,
                    # прерывать, если пользователь заговорил
                    "interrupt_response": True
                },
                "temperature": 0.7
            }
        }
        await ws.send(json.dumps(session_update))

        # Запустим фоновую задачу, которая читает ответы от модели
        # и пересылает их в телефонию
        listener_task = asyncio.create_task(realtime_listener(ws, writer))
        parser = AudioSocketParser()
        try:
            while True:
                data = await reader.read(1024)
                parser.buffer.extend(data)

                if not data:
                    break

                packet_type, packet_length, payload = parser.parse_packet()

                # Обрабатываем разные типы пакетов
                if packet_type == 0x00:
                    logger.info("Пакет закрытия соединения")
                    return

                elif packet_type == 0x01:
                    uuid = payload.hex()
                    logger.info(f"UUID получен: {uuid}")

                elif packet_type == 0x10:
                    pcm8k = AudioConverter.alaw_to_pcm(payload)

                    # Пересэмплируем 8 kHz -> 24 kHz, кодируем в base64
                    pcm24k = resample_audio(pcm8k, 8000, 24000)
                    b64_chunk = base64.b64encode(pcm24k).decode('utf-8')

                    # Отправляем в Realtime API
                    # event_append = {
                    #     "type": "input_audio_buffer.append",
                    #     "audio": b64_chunk
                    # }
                    try:
                        chunk = 512
                        for i in range(0, len(b64_chunk), chunk):
                            event_append = {
                                "type": "input_audio_buffer.append",
                                "audio": b64_chunk[i:i+chunk]
                            }
                            await ws.send(json.dumps(event_append))
                    except Exception:
                        logger.exception('HERE IS A BUG')
                        continue

                elif packet_type == 0xFF:
                    error_code = payload.decode("utf-8", errors="ignore")
                    logger.error(f"Error: {error_code}")

                else:
                    logger.info(
                        f"Непонятный тип пакета: 0x{packet_type:02x}")
        except Exception as exc:
            logger.error(exc)

        # finally:
        #     logger.info("Closing Realtime listener task...")
        #     listener_task.cancel()
        #     writer.close()
        #     await writer.wait_closed()

        logger.info("AudioSocket connection closed.")


async def main():
    HOST = '0.0.0.0'
    PORT = 7575

    server = await asyncio.start_server(
        handle_audiosocket_connection, HOST, PORT)
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f'Serving on {addrs}')
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
