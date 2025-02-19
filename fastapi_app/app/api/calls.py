from fastapi.routing import APIRouter

from fastapi_app.app.ari.ari_commands import connect_to_ari


calls_router = APIRouter()

@calls_router.post('')
async def create_call(number: int) -> str:
    await connect_to_ari()
