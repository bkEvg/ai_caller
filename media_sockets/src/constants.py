import os


DEFAULT_SAMPLE_RATE = 8000
DEFAULT_SAMPLE_WIDTH = 2
CHANNEL_COUNT = 1
DEFAULT_LANG = 'ru'

# кол-во фреймов тишины для распознавания паузы в речи
FRAMES_OF_SILENCE = 5

VAD_HARDNESS = 3

SENTENCE_TIMER = 5

REALTIME_MODEL = "gpt-4o-mini-realtime-preview-2024-12-17"
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"

OPENAI_API_KEY = os.environ.get('OPENAI_KEY')
