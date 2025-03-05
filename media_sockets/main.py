import asyncio
import logging
import socket
from typing import Optional

from src.generators.tts import SpeechGenerator
from src.detectors.audio_detector import VoiceDetector
from src.detectors.speech_transcription import SpeechTranscriptor
from src.utils import AudioBuffer, AudioConverter

logger = logging.getLogger(__name__)


class SpeechProcessor:
    def __init__(self):
        self.vad = VoiceDetector()
        self.speech_generator = SpeechGenerator()
        self.asr = SpeechTranscriptor()
        self.audio_buffer = AudioBuffer()

    def locate_speech(self, audio: bytes) -> Optional[bool]:
        """Поиск речи в потоке"""
        audio_length = len(audio)
        if audio_length == 0 or audio_length not in [160, 320, 480]:
            return
        return self.vad.is_speech(audio)

    async def handle_audio(self, audio):
        """Обработка аудио."""

        # Накапливаем буффер для распознавания речи
        pcm_audio = AudioConverter.alaw_to_pcm(audio)
        self.audio_buffer.add(pcm_audio)
        text = None

        if self.audio_buffer.is_ready():
            wav_audio = AudioConverter.pcm_to_wav(self.audio_buffer.buffer)
            text = self.asr.recognize(wav_audio)
            # self.audio_buffer.clear()
            logger.error(f'Распознано: {text}')
        if text:
            # Генерируем аудио через TTS
            return self.speech_generator.generate(text)
        return None


async def main():
    """
    Main WebSocket server.
    """
    HOST = '0.0.0.0'
    PORT = 7575
    # Start the audiosocket server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as socket_stream:
        socket_stream.bind((HOST, PORT))
        socket_stream.listen()
        speech_processor = SpeechProcessor()
        logger.error("AudioSocket server started listening.")
        conn, addr = socket_stream.accept()
        with conn:
            while True:
                data = conn.recv(160)
                if not data:
                    break
                # if speech_processor.locate_speech(data):
                #     response_pcm = await speech_processor.handle_audio(data)
                #     # if response_pcm:
                #     #     frame = AudioConverter.create_audio_frame(response_pcm)
                #     #     conn.send(frame)
                #     conn.send(data)
                print(data)


if __name__ == "__main__":
    asyncio.run(main())
