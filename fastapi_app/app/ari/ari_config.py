import base64
import os

from dotenv import load_dotenv

load_dotenv()

HOST = os.environ.get('ARI_IP')
EXTERNAL_HOST = os.environ.get('ARI_EXTERNAL_IP_HOST')
ARI_HOST = f"http://{HOST}/ari"
ARI_TIMEOUT = 60
SIP_HOST = os.environ.get('SIP_HOST')
ARI_USER = os.environ.get('ARI_USER')
ARI_PASSWORD = os.environ.get('ARI_PASS')
STASIS_APP_NAME = 'fast_api'
WEBSOCKET_HOST = f"ws://{HOST}/ari/events?app={STASIS_APP_NAME}"

# Кодируем данные для входа
auth_bytes = f'{ARI_USER}:{ARI_PASSWORD}'.encode('utf-8')
base64_auth = base64.b64encode(auth_bytes).decode('utf-8')

AUTH_HEADER = {
    'Authorization': f'Basic {base64_auth}'
}
