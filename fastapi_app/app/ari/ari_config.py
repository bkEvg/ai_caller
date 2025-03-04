import base64
import os

from dotenv import load_dotenv

load_dotenv()

HOST = '31.129.35.221:8088'
EXTERNAL_HOST = '217.114.3.34:7575'
ARI_HOST = f"http://{HOST}/ari"
ARI_USER = "terra-user-01"
ARI_PASSWORD = os.environ.get('ARI_PASS')
STASIS_APP_NAME = 'fast_api'
WEBSOCKET_HOST = f"ws://{HOST}/ari/events?app={STASIS_APP_NAME}"

SIP_ENDPOINT = 'SIP/89232391892@terraai-test'
# Кодируем данные для входа
auth_bytes = f'{ARI_USER}:{ARI_PASSWORD}'.encode('utf-8')
base64_auth = base64.b64encode(auth_bytes).decode('utf-8')

AUTH_HEADER = {
    'Authorization': f'Basic {base64_auth}'
}