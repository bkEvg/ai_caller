import asyncio
import websockets
import json
import pyaudio
import base64
import logging
import ssl
import threading

from src.constants import OPENAI_API_KEY, REALTIME_MODEL
from src.utils import AudioSocketParser, AudioConverter

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOPIC = "Поговорим о культуре в Испании."

INSTRUCTIONS = f"""
Ты просто добродушный друг из испании, который неплохо разговаривает по русски
{TOPIC}.
"""

KEYBOARD_COMMANDS = """
q: Quit
t: Send text message
a: Send audio message
"""


class AudioHandler:
    """
    Handles audio input and output using PyAudio.
    """
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.audio_buffer = b''
        self.chunk_size = 1024  # Number of audio frames per buffer
        self.format = pyaudio.paInt16  # Audio format (16-bit PCM)
        self.channels = 1  # Mono audio
        self.rate = 24000  # Sampling rate in Hz
        self.is_recording = False

    def start_audio_stream(self):
        """
        Start the audio input stream.
        """
        self.stream = self.p.open(
            format=self.format,
            channels=self.channels,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk_size
        )

    def stop_audio_stream(self):
        """
        Stop the audio input stream.
        """
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

    def cleanup(self):
        """
        Clean up resources by stopping the stream and terminating PyAudio.
        """
        if self.stream:
            self.stop_audio_stream()
        self.p.terminate()

    def start_recording(self):
        """Start continuous recording"""
        self.is_recording = True
        self.audio_buffer = b''
        self.start_audio_stream()

    def stop_recording(self):
        """Stop recording and return the recorded audio"""
        self.is_recording = False
        self.stop_audio_stream()
        return self.audio_buffer

    def record_chunk(self):
        """Record a single chunk of audio"""
        if self.stream and self.is_recording:
            data = self.stream.read(self.chunk_size)
            self.audio_buffer += data
            return data
        return None

    async def play_audio(self, audio_data, writer):
        """
        Play audio data.

        :param audio_data: Received audio data (AI response)
        :param writer: asyncio StreamWriter to send back audio data
        """
        audio_data = AudioConverter.resample_audio(audio_data, 24000, 8000)
        min_data = 160
        pause = 0.02
        for chunk in range(0, len(audio_data), min_data):
            chunk_data = AudioConverter.create_audio_packet(audio_data[chunk:chunk + min_data])
            if chunk_data:
                writer.write(chunk_data)
                await writer.drain()
                logger.debug("Playing audio")
                await asyncio.sleep(pause)
        # chunk_data = AudioConverter.create_audio_packet(audio_data)
        # writer.write(chunk_data)
        # await writer.drain()
        # logger.debug("Playing audio")


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

        self.session_config = {
            "modalities": ["audio", "text"],
            "instructions": self.instructions,
            "voice": self.voice,
            "input_audio_format": "g711_alaw",
            "output_audio_format": "pcm16",
            "temperature": 0.6
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

        if event_type == "response.audio.delta":
            # Append audio data to buffer
            audio_data = base64.b64decode(event["delta"])
            self.audio_buffer += audio_data
            logger.debug("Audio data appended to buffer")
        elif event_type == "response.audio.done":
            # Play the complete audio response
            if self.audio_buffer:
                # Создаем копию, что дальше очищение не повляло
                # на воспроизведение и не будет блокировать поток
                data = self.audio_buffer
                asyncio.create_task(
                    self.audio_handler.play_audio(data, self.writer)
                )
                logger.info("Done playing audio response")
                # А точно ли у нас копия выше, или это просто ссылка ?!
                self.audio_buffer = b''
            else:
                logger.warning("No audio data to play")

    async def send_audio(self):
        """
        Record and send audio using server-side turn detection.
        """
        logger.debug("Starting audio recording for user input")
        self.audio_handler.start_recording()

        try:
            while True:
                chunk = self.audio_handler.record_chunk()
                if chunk:
                    # Encode and send audio chunk
                    base64_chunk = base64.b64encode(chunk).decode('utf-8')
                    await self.send_event({
                        "type": "input_audio_buffer.append",
                        "audio": base64_chunk
                    })
                    await asyncio.sleep(0.01)
                else:
                    break

        except Exception as e:
            logger.error(f"Error during audio recording: {e}")
            self.audio_handler.stop_recording()

        finally:
            self.audio_handler.stop_recording()
            logger.debug("Audio recording stopped")

    async def run(self):
        """
        Main loop for handling audio socket interaction.
        """
        await self.connect()

        # Start receiving events in the background
        receive_task = asyncio.create_task(self.receive_events())
        parser = AudioSocketParser()

        try:
            while True:
                # Receive audio data from reader
                data = await self.reader.read(1024)
                if data:
                    parser.buffer.extend(data)
                    packet_type, packet_length, payload = parser.parse_packet()
                    base64_data = base64.b64encode(payload).decode('utf-8')
                    await self.send_event({
                        "type": "input_audio_buffer.append",
                        "audio": base64_data
                    })
                else:
                    break

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in audio socket communication: {e}")

        finally:
            receive_task.cancel()
            await self.cleanup()

    async def cleanup(self):
        """
        Clean up resources by closing the WebSocket and audio handler.
        """
        self.audio_handler.cleanup()
        if self.ws:
            await self.ws.close()


async def handle_audiosocket_connection(reader, writer):
    """
    Handle connection for audio socket and OpenAI Realtime communication.
    """
    logger.debug('handle_audiosocket_connection() started')
    client = AudioWebSocketClient(reader, writer, instructions=INSTRUCTIONS, voice="ash")
    await client.run()


async def main():
    """
    Main entry point for the server.
    """
    server = await asyncio.start_server(
        handle_audiosocket_connection, 'localhost', 8888
    )
    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    logger.info(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
