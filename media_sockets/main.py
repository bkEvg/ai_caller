import asyncio
import base64
import logging
import numpy as np
import os
import socket
import struct
from scipy.signal import resample_poly
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


def upsample_8k_to_16k(pcm8k: bytes) -> bytes:
    """
    Переводит массив int16 (8kHz) -> int16 (16kHz)
    Использует resample_poly(..., up=2, down=1)
    """
    data_int16 = np.frombuffer(pcm8k, dtype=np.int16)
    # float32 для ресэмплинга
    data_float = data_int16.astype(np.float32)
    # Увеличиваем частоту в 2 раза (8k -> 16k)
    upsampled = resample_poly(data_float, 2, 1)
    upsampled_int16 = upsampled.astype(np.int16)
    return upsampled_int16.tobytes()


def downsample_16k_to_8k(pcm16k: bytes) -> bytes:
    """
    Переводит массив int16 (16kHz) -> int16 (8kHz)
    Использует resample_poly(..., up=1, down=2)
    """
    data_int16 = np.frombuffer(pcm16k, dtype=np.int16)
    data_float = data_int16.astype(np.float32)
    downsampled = resample_poly(data_float, 1, 2)
    downsampled_int16 = downsampled.astype(np.int16)
    return downsampled_int16.tobytes()


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
            logger.info('Подготавливаем ответ')
            audio_b64 = event.get("delta", "")
            if audio_b64:
                pcm16k = base64.b64decode(audio_b64)
                pcm8k = downsample_16k_to_8k(pcm16k)
                logger.info(f"Длинна пакета с речью - {len(pcm8k)} байт")
                frame = AudioConverter.create_audio_packet(pcm8k)
                writer.write(frame)
                if writer.is_closing():
                    logger.warning("Writer закрывается, прерываем отправку")
                    return

                await writer.drain()

        elif event_type == "response.text.delta":
            # Если нужен текст - обрабатываем.
            text_chunk = event.get("delta", "")
            logger.info("Text chunk from model:", text_chunk)

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
                ),
                # Можно настроить VAD, температуру и т.п.
                "turn_detection": {
                    "type": "server_vad",
                    # Порог чувствительности(0.0...1.0)
                    "threshold": 0.5,
                    # Сколько миллисекунд тишины считать концом речи
                    "silence_duration_ms": 500,
                    # Сколько миллисекунд звука сохранять "до" VAD -
                    # срабатывания
                    "prefix_padding_ms": 300,
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

                    # Пересэмплируем 8 kHz -> 16 kHz, кодируем в base64
                    pcm16k = upsample_8k_to_16k(pcm8k)
                    b64_chunk = base64.b64encode(pcm16k).decode('utf-8')

                    # Отправляем в Realtime API
                    event_append = {
                        "type": "input_audio_buffer.append",
                        "audio": b64_chunk
                    }
                    await ws.send(json.dumps(event_append))

                elif packet_type == 0xFF:
                    error_code = payload.decode("utf-8", errors="ignore")
                    logger.error(f"Error: {error_code}")

                else:
                    logger.info(
                        f"Непонятный тип пакета: 0x{packet_type:02x}")

        # except Exception as e:
        #     logger.info("AudioSocket connection error:", e)
        finally:
            logger.info("Closing Realtime listener task...")
            listener_task.cancel()
            writer.close()
            await writer.wait_closed()

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
