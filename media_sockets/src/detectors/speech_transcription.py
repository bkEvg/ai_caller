from abc import ABC, abstractmethod
import json

from vosk import Model, KaldiRecognizer
import speech_recognition as sr

from src.constants import DEFAULT_SAMPLE_RATE


class Recognizer(ABC):
    """Базовый класс для разпознователей речи."""

    @abstractmethod
    def recognize(self, audio_data: bytes) -> str:
        pass


class VoskSpeechRecognizer(Recognizer):
    def __init__(self, model_path="vosk-model-ru"):
        self.model = Model(model_path)
        self.recognizer = KaldiRecognizer(self.model, DEFAULT_SAMPLE_RATE)

    def recognize(self, audio_data: bytes) -> str:
        self.recognizer.AcceptWaveform(audio_data)
        result = self.recognizer.Result()
        return json.loads(result)["text"]


class GoogleRecognizer(Recognizer):

    def __init__(self):
        self.recognizer = sr.Recognizer()

    def recognize(self, audio_data) -> str:
        with sr.AudioFile(audio_data) as source:
            audio = self.recognizer.record(source)
        try:
            return self.recognizer.recognize_google(audio, language="ru-RU")
        except sr.UnknownValueError:
            print("Sphinx could not understand audio")
        except sr.RequestError as e:
            print("Sphinx error; {0}".format(e))


class SpeechTranscriptor:
    """Класс для распознавания речи."""

    def __init__(self, service: Recognizer = GoogleRecognizer()):
        self.service = service

    def recognize(self, audio_data) -> str:
        """Распознаем текст из звука."""
        return self.service.recognize(audio_data)