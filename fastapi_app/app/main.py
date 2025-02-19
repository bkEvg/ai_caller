from fastapi import FastAPI

from .api.users import users_router
from .database import init_db

app = FastAPI(title='SIP Bot API')

@app.on_event('startup')
async def startup():
    await init_db()

app.include_router(users_router, prefix='/api/v1/users',)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, port=9000, host='0.0.0.0')
