from fastapi.routing import APIRouter
from asterisk.ami import AMIClient, AMIClientAdapter

router = APIRouter()

# Подключение к Asterisk AMI
def connect_ami():
    client = AMIClient(address='localhost', port=5038)
    client.login(username='fastapi', secret='mysecret')
    return client


@router.post("/make_call")
def make_call(phone_number: str):
    client = connect_ami()
    adapter = AMIClientAdapter(client)

    response = adapter.Originate(
        Channel=f'SIP/{phone_number}',
        Context='default',
        Exten='100',
        Priority=1,
        CallerID='FastAPI',
        Timeout=30000
    )

    client.logoff()
    return {"status": "Call initiated", "response": response}