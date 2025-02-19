import requests
import websockets
import json
import time

from .ari_config import (ARI_HOST, AUTH_HEADER, WEBSOCKET_HOST, SIP_ENDPOINT,
                         STASIS_APP_NAME)


# Функция для создания канала (звонка)
def create_channel(endpoint: str):
    """Создать канал."""
    url = f"{ARI_HOST}/channels"
    data = {
        "endpoint": endpoint,
        "app": STASIS_APP_NAME
    }
    response = requests.post(url, json=data, headers=AUTH_HEADER)
    if response.status_code == 200:
        return response.json()  # Возвращаем ID канала
    else:
        print("Ошибка при создании канала:", response.json())
        return None


# Функция для проигрывания аудио в канале
def play_audio(channel_id):
    """Проиграть запись в канале."""
    url = f"{ARI_HOST}/channels/{channel_id}/play"
    data = {
        "media": "sound:queue-minutes"  # Путь к аудио файлу на Asterisk
    }
    response = requests.post(url, json=data, headers=AUTH_HEADER)
    if response.status_code == 200:
        print("Аудио проигрывается.")
    else:
        print("Ошибка при проигрывании аудио:", response.json())


def record_call(channel_id):
    """Запись звонка."""
    url = f"{ARI_HOST}/recordings"
    data = {
        "channel": channel_id,
        "format": "wav",  # Формат записи
        "name": "client_call_recording"
    }
    response = requests.post(url, json=data, headers=AUTH_HEADER)
    if response.status_code == 200:
        print("Запись начата.")
    else:
        print("Ошибка при записи звонка:", response.json())


# Завершаем звонок
def hangup_call(channel_id):
    """Завершение звонка."""
    url = f"{ARI_HOST}/channels/{channel_id}"
    response = requests.delete(url, headers=AUTH_HEADER)
    if response.status_code == 200:
        print("Звонок завершен.")
    else:
        print("Ошибка при завершении звонка:", response.json())


async def connect_to_ari():
    uri = f"{ARI_HOST}?app={STASIS_APP_NAME}"

    async with websockets.connect(uri, extra_headers=AUTH_HEADER) as websocket:
        print(f"Connected to ARI with app {STASIS_APP_NAME}")

        # Слушаем события
        while True:
            message = await websocket.recv()
            event = json.loads(message)
            print("Received event:", event)

            # Обрабатываем событие ChannelCreated
            if event['type'] == 'ChannelCreated':
                channel_id = event['channel']['id']
                print(f"New channel created: {channel_id}")

                # Проигрываем аудио после создания канала
                play_audio(channel_id)

                # Записываем разговор
                print("Starting call recording...")
                record_call(channel_id)

                # Ждем некоторое время (например, 10 секунд), пока продолжается разговор
                time.sleep(10)

                # Завершаем звонок
                hangup_call(channel_id)
                print(f"Call {channel_id} ended.")