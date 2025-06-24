from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import logging

from app.api.calls import calls_router
from app.api.health import health_router
from app.core.config import settings


logging.basicConfig(
    level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


app = FastAPI(title=settings.APP_TITLE, description=settings.APP_DESCRIPTION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(calls_router, prefix='/api/v1/calls')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, port=9000, host='0.0.0.0')
