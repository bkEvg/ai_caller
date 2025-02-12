from fastapi import FastAPI

from api import router
from database import init_db

app = FastAPI(title='SIP Bot API')

@app.on_event('startup')
async def startup():
    await init_db()

app.include_router(router)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, port=9000)
