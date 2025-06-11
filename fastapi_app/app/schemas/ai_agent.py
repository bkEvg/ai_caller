from enum import Enum
from typing import Optional

from pydantic import (BaseModel, Field, field_validator, ValidationError,
                      ConfigDict)
from app.models.ai_agent import Phone, CallStatus


class PhoneExamples(dict, Enum):

    FIRST = {
        "phone": {
            "digits": "79232391892"
        },
        "statuses": None
    }
    WRONG = {
        'digits': 'string'
    }

    @classmethod
    def get_openapi_examples(cls):
        person_examples = {
            example.name.lower(): {
                'summary': f"{example.name.title()} example",
                'value': example
            }
            for example in cls
        }
        return person_examples


class CallStatuses(str, Enum):
    CREATED = 'CallCreated'
    STASIS_START = 'StasisStart'
    STASIS_END = 'StasisEnd'
    DIAL = 'Dial'
    CHANNEL_VARSET = 'ChannelVarset'
    CHANNEL_HANDUP = 'ChannelHangupRequest'
    CHANNEL_DESTROYED = 'ChannelDestroyed'
    CHANNEL_STATE_CHANGE = 'ChannelStateChange'
    CHANNEL_LEFT_BRIDGE = 'ChannelLeftBridge'
    CHANNEL_ENTERED_BRIDGE = 'ChannelEnteredBridge'
    CHANNEL_DIALPLAN = 'ChannelDialplan'


class CallCreate(BaseModel):
    """Schema for Creating Call instance."""

    channel_id: str
    phone: 'PhoneCreate'
    statuses: Optional[list['CallStatusDB']] = None


class CallDB(BaseModel):
    """Schema for Call model"""

    id: int
    channel_id: Optional[str]
    phone: 'PhoneDB'
    statuses: list['CallStatusDB']

    model_config = ConfigDict(from_attributes=True)


class PhoneCreate(BaseModel):
    """Schema for Phone creating."""
    digits: str

    @field_validator('digits', mode='after')
    @classmethod
    def validate_digits(cls, value: str):
        if not value.isnumeric():
            raise ValueError('Номер должен состоять из цифр')
        if not value.startswith('7'):
            raise ValueError(
                'Разрешены вызовы только на Российские номера'
            )
        return value


class PhoneDB(BaseModel):
    """Schema for Phone model"""
    digits: str

    model_config = ConfigDict(from_attributes=True)


class CallStatusCreate(BaseModel):
    """Schema for CallStatus creating."""

    status_str: CallStatuses
    call_id: int


class CallStatusDB(BaseModel):
    """Schema for CallStatus model"""

    status_str: CallStatuses

    model_config = ConfigDict(from_attributes=True)
