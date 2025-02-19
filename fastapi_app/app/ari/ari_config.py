import base64
import os

from dotenv import load_dotenv

load_dotenv()

HOST = '31.129.35.221:8088'
ARI_HOST = f"http://{HOST}/ari"
WEBSOCKET_HOST = f"ws://{HOST}/events?app=fast_api"
ARI_USER = "terra-user-01"
ARI_PASSWORD = os.environ.get('ARI_PASS')

SIP_ENDPOINT = 'SIP/phone101'
STASIS_APP_NAME = 'fast_api'
# Кодируем данные для входа
auth_bytes = f'{ARI_USER}:{ARI_PASSWORD}'.encode('utf-8')
base64_auth = base64.b64encode(auth_bytes).decode('utf-8')

AUTH_HEADER = {
    'Authorization': f'Basic {base64_auth}'
}