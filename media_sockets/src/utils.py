import asyncio
import logging

from pydub import AudioSegment
import audioop
import struct
from typing import Optional

from src.constants import (DEFAULT_SAMPLE_RATE, CHANNEL_COUNT,
                           DEFAULT_SAMPLE_WIDTH, SENTENCE_TIMER)


class AudioBuffer:
    def __init__(self, target_duration_sec=SENTENCE_TIMER,
                 sample_rate=DEFAULT_SAMPLE_RATE,
                 sample_width=DEFAULT_SAMPLE_WIDTH):
        self.buffer = bytearray()
        self.size = target_duration_sec * sample_rate * sample_width

    def add(self, data: bytes):
        self.buffer.extend(data)
        if len(self.buffer) > self.size:
            self.buffer = self.buffer[-self.size:]

    def is_ready(self):
        return len(self.buffer) >= self.size

    def clear(self):
        self.buffer.clear()


class AudioConverter:
    """Класс для конвертации аудио в разные форматы."""

    @staticmethod
    def convert_to_raw(mp3_file) -> bytes:
        """Достаем из аудио mp3 -> RAW PCM данные в одном канале и 16-бит
        глубиной."""
        audio_fragment = AudioSegment.from_mp3(mp3_file)
        audio_fragment.set_frame_rate(DEFAULT_SAMPLE_RATE).set_channels(
            CHANNEL_COUNT)
        audio_fragment.set_sample_width(DEFAULT_SAMPLE_WIDTH)
        return audio_fragment.raw_data

    @staticmethod
    def alaw_to_pcm(alaw_data):
        """Конвертация A-law в 16-bit PCM"""
        return audioop.alaw2lin(alaw_data, DEFAULT_SAMPLE_WIDTH)

    @staticmethod
    def create_audio_packet(pcm_data: bytes) -> bytes:
        """
        Создает пакет AudioSocket для отправки аудио в Asterisk.
        Формат: [тип][длина_payload][payload]
        """
        packet_type = 0x10.to_bytes(1, byteorder="big")
        payload_length = len(pcm_data).to_bytes(2, byteorder="big")
        return packet_type + payload_length + pcm_data

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


class AudioSocketParser:

    def __init__(self):
        self.buffer = bytearray()

    def parse_packet(self) -> Optional[tuple[int, int, bytes]]:
        """
        Пытаемся распарсить пакет из буфера.
        Возвращает: (тип, длина_payload, payload)
        """
        if len(self.buffer) < 3:
            return None

        header = self.buffer[:3]
        obj_type = header[0]
        payload_length = struct.unpack('>H', header[1:3])[0]

        total_length = 3 + payload_length
        if len(self.buffer) < total_length:
            return None
        payload = bytes(self.buffer[3:payload_length])
        del self.buffer[:total_length]
        return obj_type, payload_length, payload


class AudioConsumer:
    """Базовый класс для потребителей аудио данных."""

    def consume_data(self):
        """Метод который реализует логику потребления."""
        raise NotImplementedError


class AudioSocketConsumer(AudioConsumer):
    """Консьюмер для аудио сокета."""

    def __init__(self, writer):
        self.writer = writer

    async def consume_data(self, data):
        """Логика потребления для аудио сокета."""
        logging.info(f"Отправка {len(data)} байт в сокет")
        await self.writer.write(AudioConverter.create_audio_packet(data))
        await self.writer.drain()


class AudioTrasferService:

    def __init__(self, trasfer_to: AudioSocketConsumer):
        self.trasfer_to = trasfer_to
        self.buffer: bytes = b''  # Буфер для накопленных данных
        # Минимальное количество данных для отправки (160 байт на фрейм)
        self.min_data = 160
        self.pause = 0.02  # Пауза между отправкой фреймов (20 мс для 8 кГц)
        self._is_running = False  # Статус работы задачи
        self._task = None  # Задача, которая будет выполняться асинхронно

    async def consume_if_ready(self):
        """
        Задача которая отправляет данные в сервис для потребления им.
        Например, AudioSocketConsumer отправляет эти данные в сокет writer.
        """
        logging.info("Запуск задачи передачи данных от gpt в сокет.")
        while True:
            if len(self.buffer) >= self.min_data:
                logging.info(f"{len(self.buffer)} размер буффера")
                data = self.buffer[:self.min_data]
                self.buffer = self.buffer[self.min_data:]
                await self.trasfer_to.consume_data(data)
                await asyncio.sleep(self.pause)

    def add_data(self, data: bytes):
        """
        Функция добавления данных в буфер, которая при достаточном количестве
        данных, запускает задачу по передаче данных.
        """
        logging.info(f"Добавление {len(data)} байт в буфер.")
        self.buffer += data
        if (len(self.buffer) >= self.min_data
                and not self._is_running):
            self._task = asyncio.create_task(self.consume_if_ready())
            self._is_running = True

    def clear(self):
        self.buffer = b''

    def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None
        self._is_running = False
        self.clear()
