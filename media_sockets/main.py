import asyncio
import websockets
import json
import base64
import logging
import ssl
import time
import uuid

from src.constants import (OPENAI_API_KEY, REALTIME_MODEL, HOST, PORT,
                           OUTPUT_FORMAT, INPUT_FORMAT, DEFAULT_SAMPLE_RATE,
                           DEFAULT_SAMPLE_WIDTH, OPENAI_OUTPUT_RATE,
                           DRAIN_CHUNK_SIZE, READER_BYTES_LIMIT)
from src.utils import AudioSocketParser, AudioConverter
from src.instructions import INSTRUCTIONS

logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AudioHandler:
    """
    Handles audio input and output using PyAudio.
    """
    def __init__(self):
        self.audio_buffer = b''

        self.is_running = False
        self.audio_queue = asyncio.Queue()

    async def start_playback_loop(self, writer):
        if self.is_running:
            return  # уже запущено

        self.is_running = True
        while True:
            audio_data = await self.audio_queue.get()
            try:
                await self.play_audio(audio_data, writer)
            except Exception as e:
                logger.error(f"Ошибка при воспроизведении: {e}")
            self.audio_queue.task_done()

    async def enqueue_audio(self, audio_data):
        await self.audio_queue.put(audio_data)

    @staticmethod
    async def play_audio(audio_data, writer):
        logger.info(f"▶️ Старт воспроизведения: {len(audio_data)} байт")
        start = time.time()
        audio_data = AudioConverter.resample_audio(
            audio_data, OPENAI_OUTPUT_RATE, DEFAULT_SAMPLE_RATE
        )
        chunk_size = DRAIN_CHUNK_SIZE
        samples_per_chunk = chunk_size / DEFAULT_SAMPLE_WIDTH
        pause = samples_per_chunk / DEFAULT_SAMPLE_RATE

        for chunk in range(0, len(audio_data), chunk_size):
            chunk_data = AudioConverter.create_audio_packet(
                audio_data[chunk:chunk + chunk_size]
            )
            if chunk_data:
                writer.write(chunk_data)
                await writer.drain()
                await asyncio.sleep(pause)
        duration = time.time() - start
        logger.info(f"✅ Воспроизведение завершено, длина: {duration:.2f} сек")


class AudioWebSocketClient:
    """
    Handles interaction with OpenAI Realtime API via WebSocket.
    Adapted to work with reader and writer for audio socket communication.
    """
    def __init__(self, reader, writer, instructions, voice="alloy"):
        self.reader = reader
        self.writer = writer
        self.url = "wss://api.openai.com/v1/realtime"
        self.model = REALTIME_MODEL
        self.api_key = OPENAI_API_KEY
        self.ws = None
        self.audio_handler = AudioHandler()

        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        self.audio_buffer = b''
        self.instructions = instructions
        self.voice = voice

        # VAD mode (set to null to disable)
        self.VAD_turn_detection = True
        self.VAD_config = {
            "type": "server_vad",
            # Activation threshold (0.0-1.0). A higher threshold will require
            # louder audio to activate the model.
            "threshold": 0.3,
            # Audio to include before the VAD detected speech.
            "prefix_padding_ms": 300,
            # Silence to detect speech stop. With lower values the model
            # will respond more quickly.
            "silence_duration_ms": 200
        }

        self.session_config = {
            "modalities": ["audio", "text"],
            "instructions": self.instructions,
            "voice": self.voice,
            "input_audio_format": INPUT_FORMAT,
            "output_audio_format": OUTPUT_FORMAT,
            "turn_detection": (
                self.VAD_config if self.VAD_turn_detection else None
            ),
            "input_audio_transcription": {  # Get transcription of user turns
                "model": "whisper-1"
            },
            "temperature": 0.7
        }

    async def connect(self):
        """
        Connect to the WebSocket server.
        """
        logger.info(f"Connecting to WebSocket: {self.url}")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1"
        }

        self.ws = await websockets.connect(
            f"{self.url}?model={self.model}",
            additional_headers=headers,
            ssl=self.ssl_context
        )
        logger.info("Successfully connected to OpenAI Realtime API")

        await self.send_event({
            "type": "session.update",
            "session": self.session_config
        })
        logger.info("Session set up")

    async def send_event(self, event):
        """
        Send an event to the WebSocket server.
        """
        await self.ws.send(json.dumps(event))
        logger.debug(f"Sent event: {event}")

    async def receive_events(self):
        """
        Continuously receive events from the WebSocket server.
        """
        try:
            async for message in self.ws:
                event = json.loads(message)
                await self.handle_event(event)
        except websockets.ConnectionClosed as e:
            logger.error(f"WebSocket connection closed: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")

    async def handle_event(self, event):
        """
        Handle incoming events from the WebSocket server.
        """
        event_type = event.get("type")
        logger.debug(f"Received event type: {event_type}")

        if event_type == "error":
            logger.error(f"Error event received: {event['error']['message']}")

        elif event_type == "response.text.delta":
            # Print text response incrementally
            logger.info(event["delta"])

        elif event_type == "response.audio.delta":
            # Append audio data to buffer
            logger.info("Часть ответа добавляется в буффер на проигрывание")
            audio_data = base64.b64decode(event["delta"])
            await self.audio_handler.enqueue_audio(audio_data)
        elif event_type == "response.done":
            logger.info("Response generation completed")
        elif event_type == "conversation.item.created":
            logger.info(f"Conversation item created: {event.get('item')}")
        elif event_type == "input_audio_buffer.speech_started":
            logger.info("Speech started detected by server VAD")
        elif event_type == "input_audio_buffer.speech_stopped":
            logger.info("Speech stopped detected by server VAD")
        elif event_type == "response.content_part.done":
            pass
        elif event_type == 'response.audio_transcript.done':
            logger.info(event["delta"])
        else:
            logger.info(f"Unhandled event type: {event_type}")

    async def run(self):
        """
        Main loop for handling audio socket interaction.
        """
        await self.connect()

        # Start playing data from Queue
        asyncio.create_task(
            self.audio_handler.start_playback_loop(self.writer)
        )

        # Start receiving events in the background
        receive_task = asyncio.create_task(self.receive_events())
        parser = AudioSocketParser()

        try:
            while True:
                # Receive audio data from reader
                data = await self.reader.read(READER_BYTES_LIMIT)
                if data:
                    parser.buffer.extend(data)
                    packet_type, packet_length, payload = parser.parse_packet()
                    if packet_type == 0x10:
                        base64_data = base64.b64encode(payload).decode('utf-8')
                        await self.send_event({
                            "type": "input_audio_buffer.append",
                            "audio": base64_data
                        })
                    elif packet_type == 0x01:
                        logger.info(f"Получен UUID потока: {payload}")
                    else:
                        logger.warning(f"Получен не голосовой пакет. Тип: {hex(packet_type)}, длина: {packet_length}")
                else:
                    logger.error('No data from external media')

        except Exception as e:
            logger.error(f"Error in audio socket communication: {e}")

        finally:
            receive_task.cancel()
            await self.cleanup()

    async def cleanup(self):
        """
        Clean up resources by closing the WebSocket and audio handler.
        """
        if self.ws:
            await self.ws.close()


async def handle_audiosocket_connection(reader, writer):
    """
    Handle connection for audio socket and OpenAI Realtime communication.
    """
    logger.debug('handle_audiosocket_connection() started')
    client = AudioWebSocketClient(reader, writer, INSTRUCTIONS)
    await client.run()


async def main():
    """
    Main entry point for the server.
    """
    server = await asyncio.start_server(
        handle_audiosocket_connection, HOST, PORT
    )
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
