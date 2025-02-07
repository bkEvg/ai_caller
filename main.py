from fastapi import FastAPI

from api.routes import router

app = FastAPI(title='SIP Bot API')

app.include_router(router)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, port=9000)
