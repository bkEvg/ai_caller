from fastapi.routing import APIRouter, HTTPException

from ..users.models import User
from ..users.schemas import UserCreate, UserRead

users_router = APIRouter()


@users_router.post('', response_model=UserRead)
async def create_user(user: UserCreate):
    """Создание пользователя."""
    user_exist = await User.filter(email=user.email).first()
    if user_exist:
        raise HTTPException(status_code=400, detail='Email alredy registered')
    new_user = await User.create(**user.dict())
    return UserRead.model_validate(new_user)

@users_router.get('/{user_id}', response_model=UserRead)
async def get_user(user_id: int):
    """Получение пользователя."""
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return UserRead.model_validate(user)
