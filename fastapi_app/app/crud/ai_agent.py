from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.ai_agent import Call, Phone, CallStatus
from app.schemas.ai_agent import (CallCreate, PhoneCreate, CallStatusCreate,
                                  CallStatusDB)
from app.core.db import AsyncSessionLocal


async def create_call(call_data: CallCreate) -> Call:
    """Create Call object."""
    phone_obj = await get_phone_by_digits(call_data.phone.digits)
    async with AsyncSessionLocal() as session:
        if not phone_obj:
            # Создаём Phone из вложенной схемы
            phone_obj = Phone(digits=call_data.phone.digits)

        # Создаём Call
        call_obj = Call(phone=phone_obj, channel_id=call_data.channel_id)

        # Создаём CallStatus объекты, если есть
        if call_data.statuses:
            call_obj.statuses = [
                CallStatus(status_str=status.status_str)
                for status in call_data.statuses
            ]

        session.add(call_obj)
        await session.commit()
        await session.refresh(call_obj)
        query = (
            select(Call)
            .options(joinedload(Call.phone), joinedload(Call.statuses))
            .where(Call.id == call_obj.id)
        )
        result = await session.scalar(query)
    return result


# Phone

async def create_phone(phone_data: PhoneCreate):
    """Create Phone object in db."""
    instance = Phone(**phone_data.model_dump())
    async with AsyncSessionLocal() as session:
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
    return instance


async def get_phone_by_digits(digits: str) -> Optional[Phone]:
    async with AsyncSessionLocal() as session:
        query = select(Phone).where(Phone.digits == digits)
        phone = await session.scalar(query)
    return phone


async def delete_phone_by_digits(digits: str) -> None:
    async with AsyncSessionLocal() as session:
        phone = await session.scalar(select(Phone).where(Phone.digits == digits))
        if phone:
            await session.delete(phone)
            await session.commit()


# Call

async def get_call_by_channel(channel_id: str) -> Optional[Call]:
    async with AsyncSessionLocal() as session:
        query = select(Call).where(Call.channel_id == channel_id)
        call = await session.scalar(query)
    return call


async def get_call_by_id(id: str) -> Optional[Call]:
    async with AsyncSessionLocal() as session:
        query = select(Call).where(Call.id == id)
        call = await session.scalar(query)
    return call


async def get_calls_by_phone_digits(digits: int) -> List[Call]:
    phone_obj = await get_phone_by_digits(digits)
    async with AsyncSessionLocal() as session:
        query = select(Call).options(
            joinedload(Call.phone), joinedload(Call.statuses)
        ).where(Call.phone == phone_obj)
        result = await session.execute(query)
    return result.unique().scalars().all()


# CallStatus

async def create_call_status(call_status_data: CallStatusCreate) -> CallStatus:
    async with AsyncSessionLocal() as session:
        status = CallStatus(**call_status_data.model_dump())
        session.add(status)
        await session.commit()
        await session.refresh(status)
    return status


async def append_status_to_call(channel_id: str, statuses: list[CallStatusDB]) -> Call:
    async with AsyncSessionLocal() as session:
        query = select(Call).where(Call.channel_id == channel_id)
        call: Call = await session.scalar(query)
        if not call:
            raise ValueError(f'Звонок с channel_id={channel_id} не найден.')

        for status in statuses:
            status_obj = CallStatus(call_id=call.id, **status.model_dump())
            session.add(status_obj)

        await session.commit()
        await session.refresh(call)
    return call


async def get_statuses_for_call(call_id: int) -> List[CallStatus]:
    async with AsyncSessionLocal() as session:
        query = select(CallStatus).where(
            CallStatus.call_id == call_id).order_by(CallStatus.created_at)
        result = await session.scalars(query)
    return result.all()
