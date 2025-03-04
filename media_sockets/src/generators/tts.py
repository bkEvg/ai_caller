from abc import ABC, abstractmethod
import io
import logging

from gtts import gTTS

from src.constants import (DEFAULT_LANG, DEFAULT_SAMPLE_RATE,
                         DEFAULT_SAMPLE_WIDTH)
from src.utils import AudioConverter


class Speech(ABC):
    """Базовый класс, для интерфейсов которые генерируют речь."""

    @abstractmethod
    def generate_speech(self, text: str) -> bytes:
        pass


class GoogleSpeech(Speech):
    """Интерфейс для получения речи из текста с помощью решения от Google."""
    def generate_speech(self, text: str) -> bytes:
        tts = gTTS(text, lang=DEFAULT_LANG)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return buffer.read()


class SpeechGenerator:
    """Класс обертка для интерфейса генерации речи."""

    def __init__(self, service: Speech = GoogleSpeech()):
        self.service = service

    def generate(self, text: str, format=None) -> bytes:
        """
        Сгенерировать аудио файл из текста.
        По умолчанию возвращается RAW PCM файл, также доступен mp3
        """
        audio = self.service.generate_speech(text)
        if not format:
            audio = AudioConverter.convert_to_raw(audio)
            logging.error(type(audio))
            return audio
        elif format == 'mp3':
            return audio
