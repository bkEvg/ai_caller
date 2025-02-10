from fastapi.routing import APIRouter
from asterisk.ami import AMIClient, AMIClientAdapter, FutureResponse

router = APIRouter()

# Подключение к Asterisk AMI
def connect_ami():
    client = AMIClient(address='localhost', port=5038)
    client.login(username='fastapi', secret='mysecret')
    return client

@router.post("/make_call")
def make_call(phone_number: str):
    try:
        # Подключаемся к AMI
        client = connect_ami()
        adapter = AMIClientAdapter(client)

        # Выполняем вызов
        response = adapter.Originate(
            Channel=f'SIP/{phone_number}',
            Context='default',
            Exten='100',
            Priority=1,
            CallerID='FastAPI',
            Timeout=30000
        )
        # Отключаемся от AMI
        client.logoff()

        return {"status": "Call initiated", "response": response.get_response()}

    except Exception as e:
        # Логируем ошибку и возвращаем сообщение об ошибке
        return {"status": "Error", "message": str(e)}