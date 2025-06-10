from typing import Optional

from sqlalchemy import select

from app.models.ai_agent import Call, Phone
from app.schemas.ai_agent import PhoneRequest
from app.core.db import AsyncSessionLocal


async def create_phone(phone: PhoneRequest):
    """Create Phone object in db."""
    phone_data = phone.model_dump()
    instance = Phone(**phone_data)
    async with AsyncSessionLocal() as session:
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
    return instance


async def get_phone(phone: PhoneRequest) -> Optional[Phone]:
    """Get Phone instance from db."""
    async with AsyncSessionLocal() as session:
        query = select(Phone).where(Phone.digits == phone.digits)
        instance = await session.scalar(query)
    return instance


async def create_call(phone: Phone, **kwargs) -> Call:
    """Create Phone object in db."""
    call_obj = Call(phone=phone, **kwargs)
    async with AsyncSessionLocal() as session:
        session.add(call_obj)
        await session.commit()
        await session.refresh(call_obj)
    return call_obj


# def get_call(id: str) -> Optional[Phone]:
#     """Get Phone instance from db."""
#     with AsyncSessionLocal() as session:
#         query = select(Phone).where(Phone.digits == phone.digits)
#         instance = session.scalar(query)
#     return instance
