from abc import ABC, abstractmethod
import logging

import webrtcvad

from src.constants import DEFAULT_SAMPLE_RATE, VAD_HARDNESS


class VAD(ABC):
    """
    Базовый класс для всех определителей голоса.
    Должен иплементировать метод **contains_speech**
    """

    @abstractmethod
    def contains_speech(self, audio_data) -> bool:
        pass


class WebRTCDetector(VAD):
    """Интерфейс для взаимодейтсвия с распознаванием."""

    def __init__(self, level: int = VAD_HARDNESS,
                 sample_rate: int = DEFAULT_SAMPLE_RATE):
        self.vad = webrtcvad.Vad(level)
        self.sample_rate = sample_rate

    def contains_speech(self, audio_data) -> bool:
        """Определяем, присутствует ли в аудио байтах разговор."""
        return self.vad.is_speech(audio_data, self.sample_rate)


class VoiceDetector(ABC):
    """Класс для определения разговора."""

    def __init__(self, service: VAD = WebRTCDetector()):
        self.service = service

    def is_speech(self, data):
        """Присутствует ли в аудио разговор."""
        try:
            return self.service.contains_speech(data)
        except Exception:
            logging.error(f'Длина данных при ошибке {len(data)}')
