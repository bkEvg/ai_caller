from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.calls import calls_router

app = FastAPI(title='SIP Bot API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(calls_router, prefix='/api/v1/calls')


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, port=9000, host='0.0.0.0')
