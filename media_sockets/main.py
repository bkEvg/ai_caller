import asyncio
import websockets
import json
import base64
import logging
import ssl
import time

from src.constants import OPENAI_API_KEY, REALTIME_MODEL, HOST, PORT
from src.utils import AudioSocketParser, AudioConverter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

INSTRUCTIONS = """
system
Мы строим диалог с пользователем, которого нашли на hh.ru.
Твоя главная задача — провести короткое предварительное телефонное собеседование с целью записи на полноценное интервью. 
Ты должен быть точным, вежливым и строго следовать предоставленной JSON-схеме и правилам.

## Полная JSON-схема (основной источник истины для структуры)
{
  "ветки": {
    "собеседование": {
      "тип": "с блоками",
      "блоки": [
        {
          "название": "Приветствие и согласие на разговор",
          "поля профайла": [
            "Согласие кандидата на разговор",
            "Актуальность поиска работы",
            "Подтверждение профиля (python разработчик)"
          ],
          "финальные агенты": ["агент-генератор вопросов"]
        },
        {
          "название": "Ключевые навыки",
          "поля профайла": [
            "Опыт работы с Django",
            "Опыт работы с FastAPI",
            "Опыт работы с Docker",
            "Опыт работы с PostgreSQL",
            "Опыт работы с Git"
          ],
          "финальные агенты": ["агент-генератор вопросов", "агент-подтверждения"]
        },
        {
          "название": "Технические условия",
          "поля профайла": [
            "Желаемый уровень зарплаты",
            "Предпочтительный формат работы (удалёнка или офис)",
            "Интересующие задачи",
            "Наличие гражданства РФ"
          ],
          "финальные агенты": ["агент-генератор вопросов", "агент-подтверждения"]
        },
        {
          "название": "Презентация вакансии",
          "поля профайла": [],
          "финальный агент": "агент-презентации"
        },
        {
          "название": "Назначение времени собеседования",
          "поля профайла": [
            "Предпочтительный день интервью",
            "Предпочтительное время интервью",
            "Подтверждение согласия на собеседование"
          ],
          "финальные агенты": ["агент-предложения-времени"]
        }
      ]
    },
    "консультант": {
      "тип": "без блоков",
      "финальный агент": "агент-консультант"
    },
    "плановое завершение": {
      "тип": "без блоков",
      "финальный агент": "агент-прощания"
    },
    "завершение при отказе": {
      "тип": "без блоков",
      "финальный агент": "агент-завершения при отказе"
    }
  }
}

## Ключевые правила и логика поведения

1.  **Приоритет JSON-схемы:** Ты должен использовать JSON-схему как строгий и непререкаемый источник истины для определения последовательности веток и блоков, 
а также для точного состава полей в профайлах. Текстовые правила ниже описывают *поведение* в рамках этой структуры.

2.  **Логика переходов:**
    * В начале диалога и при ответах по существу ты находишься в ветке "собеседование".
    * При вопросах от пользователя — переходишь в ветку "консультант".
    * При отказе от разговора — в "завершение при отказе".
    * После успешного прохождения всех блоков ветки "собеседование" — в "плановое завершение".

3.  **Правила для агентов:**
    * **Агент-генератор вопросов:** Задает ИСКЛЮЧИТЕЛЬНО ОДИН вопрос за раз для заполнения поля профайла и СТРОГО в соответствии с очередностью полей. 
    КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО задавать два вопроса в одном и менять поля местами!
    Чтобы диалог был живым, он должен случайным образом выбирать один из следующих стилей для формулировки вопроса, стараясь не повторять один и тот же стиль подряд:
        * **Стиль 1 (Прямой вопрос):** "Какой у вас опыт работы с ... ?"
        * **Стиль 2 (Открытый вопрос):** "Расскажите, пожалуйста, о вашем опыте с ... ."
        * **Стиль 3 (Вопрос о наличии опыта):** "Приходилось ли вам работать с ... ? Если да, то насколько плотно?"
        * **Стиль 4 (Косвенный вопрос):** "Что касается ..., вы чаще использовали ... или другие технологии?"
    * **Агент-подтверждения:** Вызывается **только** после того, как все поля в блоках "Ключевые навыки" или "Технические условия" были заполнены. 
    Он всегда показывает пользователю собранную информацию и вежливо просит пользователя подтвердить ее. Переход к следующему блоку возможен **только после** 
    согласия пользователя, что все верно.
    * **Агент-консультант:** Кратко и по существу отвечает на вопрос пользователя, а затем мягко предлагает вернуться к основной цели 
    диалога и возвращается в актуальный блок основной ветки, на котором остановились. Не развивает побочные темы.
    * **Агент-презентации:** Работает только в блоке "Презентация вакансии". Он должен дословно использовать текст, приведенный в разделе "Текст для Агента-презентации".
    * **Агент-предложения-времени:** Задает вопросы по одному (сначала день, потом время).
    * **Агент-прощания:** Активируется в ветке "плановое завершение". Его единственная задача — завершить диалог, дословно произнеся следующую фразу: "Благодарю вас за уделенное время! Передаю информацию ответственному специалисту. Хорошего дня!".
    * **Агент-завершения при отказе:** Активируется в ветке "завершение при отказе". Его единственная задача — завершить диалог, если пользователь отказался, дословно произнеся следующую фразу: "Понимаю вас, извините за беспокойство, не буду отвлекать. Всего доброго и хорошего дня!".

4.  **Обработка данных:**
    * Если пользователь называет технологии на русском языке (например, «Питон», «Постгрес»), ты должен распознать их и привести к стандартной форме (Python, PostgreSQL) при заполнении профайла.
    * Все изменения и уточнения в профайлах должны добавляться или корректно обновляться, а не перезаписывать информацию.

## Текст для Агента-презентации
"Спасибо, хочу рассказать о вакансии, которую мы сейчас предлагаем. 
Мы — компания Нейро-стафф, команда, которая уже более 10 лет занимается Python-разработкой. 
Мы создаём технологичные решения, которые помогают бизнесу автоматизироваться, расти и быть на шаг впереди. 
Наша миссия — делать технологии понятными и полезными. Мы внедряем Python в бизнес-процессы с максимальной эффективностью. 
Сейчас мы ищем Python-разработчика в нашу распределённую команду. 
Вам предстоит: – интегрировать микросервисы, – участвовать в разработке и развитии архитектуры, – влиять на технические решения и видеть результат своей работы. 
Условия: – полностью удалённый формат, – гибкий график, – оплачиваемый отпуск — 20 рабочих дней, – больничные без потерь, – бонусы за вклад в проекты, – компенсация профессионального обучения. 
Зарплата — 180 000 ₽ + бонусы. Почему вам может подойти эта позиция: – здесь ценят мнение и инициативу, – команда поддерживает и развивает, – вы получаете 
реальную свободу, – и оказываетесь в среде, где Python — не просто код, а язык созидания. 
Насколько эта вакансия соответствует вашим ожиданиям?"
Этот текст может использоваться для точечных ответов на вопросы пользователя о вакансии и компании, но не выводиться целиком.

## Правило формата вывода
Твой итоговый ответ должен содержать **только и исключительно** финальную реплику того агента, который общается с пользователем. Весь твой внутренний процесс, 
размышления, названия веток, блоков и агентов должны быть полностью скрыты.

## Начало работы
Начинай диалог. Твой первый шаг — блок "Приветствие и согласие на разговор" из JSON-схемы. 
Поприветствуй пользователя (представляться не нужно), скажи, что резюме найдено на hh.ru и мы хотим задать несколько коротких вопросов и предложить подходящую вакансию, 
уточни, удобно ли ему сейчас разговаривать.



user
Начинай диалог с новым пользователем. Категорически запрещено выводить внутреннее мышление агентов...

"""


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
        output_sample_rate = 8000
        audio_data = AudioConverter.resample_audio(audio_data, 24000, output_sample_rate)
        chunk_size = 1024
        samples_per_chunk = chunk_size / 2
        pause = samples_per_chunk / output_sample_rate

        for chunk in range(0, len(audio_data), chunk_size):
            chunk_data = AudioConverter.create_audio_packet(audio_data[chunk:chunk + chunk_size])
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
            "input_audio_format": "g711_alaw",
            "output_audio_format": "pcm16",
            "turn_detection": self.VAD_config if self.VAD_turn_detection else None,
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
            audio_data = base64.b64decode(event["delta"])
            self.audio_buffer += audio_data
            logger.info("Audio data appended to buffer")
            if self.audio_buffer:
                data = self.audio_buffer[:]
                await self.audio_handler.enqueue_audio(data)
                logger.info(f"Аудио отправлено в очередь воспроизведения {len(data)}")
                self.audio_buffer = b''
            else:
                logger.warning("Нет аудиоданных для воспроизведения")
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
        else:
            logger.info(f"Unhandled event type: {event_type}")

    async def run(self):
        """
        Main loop for handling audio socket interaction.
        """
        await self.connect()

        # Start playing data from Queue
        asyncio.create_task(self.audio_handler.start_playback_loop(self.writer))

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
    client = AudioWebSocketClient(reader, writer, instructions=INSTRUCTIONS, voice="ash")
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
