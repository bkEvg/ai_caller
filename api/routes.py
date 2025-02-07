from fastapi.routing import APIRouter

router = APIRouter()


@router.post('/call')
async def start_call(phone_number: str):
    """Запускает звонок на указанный номер."""
    return {"status": "Звонок выполнен", "phone": phone_number}
