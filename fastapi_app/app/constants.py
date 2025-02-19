import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

PG_USER = os.environ.get('POSTGRES_USER')
PG_PASS = os.environ.get('POSTGRES_PASSWORD')
PG_DB = os.environ.get('POSTGRES_DB')
PG_HOST = os.environ.get('POSTGRES_HOST')

POSTGRES_URL = f"postgres://{PG_USER}:{PG_PASS}@{PG_HOST}/{PG_DB}"
