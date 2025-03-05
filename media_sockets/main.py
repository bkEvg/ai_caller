import asyncio
import logging
import socket
from typing import Optional

from src.generators.tts import SpeechGenerator
from src.detectors.audio_detector import VoiceDetector
from src.detectors.speech_transcription import SpeechTranscriptor
from src.utils import AudioBuffer, AudioConverter, AudioSocketParser

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
        parser = AudioSocketParser()
        logger.error("AudioSocket server started listening.")
        conn, addr = socket_stream.accept()
        with conn:
            while True:
                data = conn.recv(160)

                # Добавляем данные в буфер
                parser.buffer.extend(data)
                while True:
                    packet = parser.parse_packet()
                    if not packet:
                        return
                    packet_type, payload_length, payload = packet

                    # Обрабатываем разные типы пакетов
                    if packet_type == 0x00:
                        logger.error("Terminate packet received")
                        return

                    elif packet_type == 0x01:
                        uuid = payload.hex()
                        logger.error(f"UUID received: {uuid}")

                    elif packet_type == 0x10:
                        logger.error(f"Audio packet: {len(payload)} bytes")
                        # Для отладки сохраняем аудио в файл
                        with open("audio.pcm", "ab") as f:
                            f.write(payload)

                    elif packet_type == 0xFF:
                        error_code = payload.decode("utf-8", errors="ignore")
                        logger.error(f"Error: {error_code}")

                    else:
                        logger.error(
                            f"Unknown packet type: 0x{packet_type:02x}")


if __name__ == "__main__":
    asyncio.run(main())
