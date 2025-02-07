from fastapi.routing import APIRouter
import asterisk.manager

router = APIRouter()


@router.post("/make_call")
def make_call(phone_number: str):
    manager = asterisk.manager.Manager()
    manager.connect('localhost')
    manager.login('fastapi', 'mysecret')

    response = manager.originate(
        channel=f'SIP/{phone_number}',
        context='default',
        exten='100',
        priority=1,
        caller_id='FastAPI',
        timeout=30000
    )

    manager.close()
    return {"status": "Call initiated", "response": response}