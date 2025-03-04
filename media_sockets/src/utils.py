from pydub import AudioSegment
import audioop
import struct
import io
import wave

from src.constants import (FRAMES_OF_SILENCE, DEFAULT_SAMPLE_RATE,
                           DEFAULT_SAMPLE_WIDTH, SENTENCE_TIMER,
                           CHANNEL_COUNT, SENTENCE_TIMER)


class AudioBuffer:
    def __init__(self, target_duration_sec=SENTENCE_TIMER, sample_rate=DEFAULT_SAMPLE_RATE,
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
    def pcm_to_alaw(pcm_data):
        """Конвертация PCM в A-law."""
        return audioop.lin2alaw(pcm_data, DEFAULT_SAMPLE_WIDTH)

    @staticmethod
    def create_audio_frame(pcm_data: bytes) -> bytes:
        """
        Создает фрейм для AudioSocket:
        - Тип: 0x10 (аудио, 16-bit PCM, 8 kHz, mono)
        - Длина данных: 2 байта (big-endian)
        - Данные: PCM-аудио
        """
        header_type = 0x10
        # Big-Endian
        header = struct.pack('!BH', header_type, len(pcm_data))
        return header + pcm_data

    @staticmethod
    def pcm_to_wav(pcm_data, sample_rate=DEFAULT_SAMPLE_RATE,
                   channels=1, sampwidth=DEFAULT_SAMPLE_WIDTH):
        """Конвертация raw PCM в WAV (используется для распознавания)"""
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sampwidth)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        wav_buffer.seek(0)
        return wav_buffer
