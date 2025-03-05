import asyncio
import socket
import struct
import base64
import json
import numpy as np
from scipy.signal import resample_poly
import websockets

# Реализация AudioSocket-фрейма:
#  - type=0x10: 16-bit PCM, 8 kHz, mono
#  - длина payload (2 байта, big-endian)


def create_audio_frame(pcm_data: bytes) -> bytes:
    """
    Формирует заголовок + PCM:
      1 байт: type=0x10
      2 байта big-endian: длина
      далее сами байты pcm_data
    """
    header_type = 0x10
    header = struct.pack('!BH', header_type, len(pcm_data))
    return header + pcm_data


def parse_audio_frame(frame: bytes) -> bytes:
    """
    Если нужно распарсить пришедший фрейм AudioSocket (type=0x10),
    возвращаем только полезную нагрузку PCM.
    Для упрощения здесь предполагается, что frame уже
    отделён от заголовков, либо мы знаем точно что это аудио.
    """
    # Если приходят "сырые" 160 байт, вероятно это уже "данные без заголовка",
    # но строго по протоколу нужно читать 3-байтовый заголовок type+length
    # и потом - payload. Ниже - для иллюстрации, как это делать.

    # frame[0] = 0x10
    # length = frame[1:3] (big-endian)
    # payload = frame[3:]
    # но иногда в Asterisk-примерах просто 160 байт ровно - уже PCM.
    # Проверяйте, как реально отправляет ваша система!

    if len(frame) < 3:
        return b""
    # Распакуем заголовок
    t, length = struct.unpack('!BH', frame[:3])
    if t != 0x10:
        return b""
    payload = frame[3:]
    if len(payload) != length:
        return b""
    return payload


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

# Для примера объединим код сервера AudioSocket и WebSocket клиент к Realtime API
# в одной асинхронной функции main().
# В реальном коде, возможно, лучше держать их в разных задачах/потоках.


REALTIME_MODEL = "gpt-4o-mini-realtime-preview-2024-12-17"
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"

OPENAI_API_KEY = "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"


async def realtime_listener(websocket, conn):
    """
    Задача, которая получает события от Realtime API
    и отправляет аудио обратно в телефонию.
    """
    while True:
        # Ждём следующего server->client сообщения от Realtime API
        msg = await websocket.recv()
        event = json.loads(msg)
        event_type = event.get("type", "")

        # Модель присылает аудио частями через response.audio.delta
        if event_type == "response.audio.delta":
            audio_b64 = event.get("delta", "")
            if audio_b64:
                pcm16k = base64.b64decode(audio_b64)
                pcm8k = downsample_16k_to_8k(pcm16k)
                frame = create_audio_frame(pcm8k)
                conn.send(frame)

        elif event_type == "response.text.delta":
            # Если нужен текст - обрабатываем.
            text_chunk = event.get("delta", "")
            print("Text chunk from model:", text_chunk)

        elif event_type == "response.done":
            print("Response finished:", event)

        else:
            # Для отладки
            # print("Other event:", event)
            pass

async def handle_audiosocket_connection(conn):
    """
    Обработка одного входящего TCP-соединения AudioSocket.
    Здесь читаем входящие 8k-пакеты и отправляем их в Realtime API.
    Возвращаем управление, когда клиент (телефония) закрыла соединение.
    """
    # Устанавливаем WebSocket-соединение с Realtime API
    async with websockets.connect(
        REALTIME_URL,
        extra_headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1"
        }
    ) as ws:
        print("Connected to Realtime API.")

        # Настраиваем сессию: audio input/output, PCM16
        session_update = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",

                # Меняем голос (например, есть "alloy", возможно будут другие)
                "voice": "shimmer",  # 'alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', and 'verse'
                # Общий стиль (тон голоса, запреты на слова, "характер" ассистента):
                "instructions": (
                    "Ты дружелюбный, мягко говорящий ассистент. "
                    "Говори с небольшой улыбкой, делай лёгкие паузы. "
                    "Избегай резких интонаций."
                ),
                # Можно настроить VAD, температуру и т.п.
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,  # Порог чувствительности(0.0...1.0)
                    "silence_duration_ms": 500,  # Сколько миллисекунд тишины считать концом речи
                    "prefix_padding_ms": 300,  # Сколько миллисекунд звука сохранять "до"  VAD - срабатывания
                    "create_response": True,  # по умолчанию true
                    "interrupt_response": True  # прерывать, если пользователь заговорил
                },
                "temperature": 0.7
            }
        }
        await ws.send(json.dumps(session_update))

        # Запустим фоновую задачу, которая читает ответы от модели
        # и пересылает их в телефонию
        listener_task = asyncio.create_task(realtime_listener(ws, conn))

        try:
            while True:
                # Читаем ~3+N байт заголовка + pcm (или сразу 160 байт,
                # зависит от того, как Asterisk/телефония реально шлет).
                packet = conn.recv(2048)
                if not packet:
                    break

                # Возможно, нужно убедиться, что это аудиофрейм (0x10),
                # распаковать заголовок, достать payload.
                # Для простоты покажем, будто у нас уже чистый PCM на 8 kHz:
                # Если вы уверены, что пакет ровно 160 байт PCM -
                # можно использовать packet напрямую
                pcm8k = packet  # или parse_audio_frame(packet)

                # Пересэмплируем 8 kHz -> 16 kHz, кодируем в base64
                pcm16k = upsample_8k_to_16k(pcm8k)
                b64_chunk = base64.b64encode(pcm16k).decode('utf-8')

                # Отправляем в Realtime API
                # (модель автоматически отслеживает паузы по VAD)
                event_append = {
                    "type": "input_audio_buffer.append",
                    "audio": b64_chunk
                }
                await ws.send(json.dumps(event_append))

        except Exception as e:
            print("AudioSocket connection error:", e)
        finally:
            print("Closing Realtime listener task...")
            listener_task.cancel()
            # При желании можно отправить "input_audio_buffer.commit" или "session.end"
            # но при разрыве всё равно сессия закроется.

        print("AudioSocket connection closed.")


async def main():
    HOST = '0.0.0.0'
    PORT = 7575

    # Запускаем TCP-сервер, который принимает ровно одно соединение
    # (или можете делать цикл и принимать несколько)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, PORT))
        sock.listen()
        print(f"AudioSocket server listening on {HOST}:{PORT}...")

        while True:
            conn, addr = sock.accept()
            print(f"New AudioSocket client: {addr}")
            # Передадим управление асинхронной handle-функции:
            await handle_audiosocket_connection(conn)
            conn.close()

if __name__ == "__main__":
    asyncio.run(main())
