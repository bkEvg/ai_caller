from fastapi.routing import APIRouter

router = APIRouter()

@router.post("/make_call")
def make_call(phone_number: str):
    try:
        return {"status": "Call initiated", "response": phone_number}
    except Exception as e:
        # Логируем ошибку и возвращаем сообщение об ошибке
        return {"status": "Error", "message": str(e)}