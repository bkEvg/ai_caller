from pydub import AudioSegment
import audioop
import struct
from typing import Optional

from src.constants import (DEFAULT_SAMPLE_RATE, CHANNEL_COUNT,
                           DEFAULT_SAMPLE_WIDTH)


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
