from enum import Enum
from typing import Optional

from pydantic import (BaseModel, Field, field_validator, ValidationError,
                      ConfigDict)
from app.models.ai_agent import Phone, CallStatus


class PhoneExamples(dict, Enum):

    FIRST = {
        'digits': '79117772200'
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


class CallCreate(BaseModel):
    """Schema for Creating Call instance."""

    phone: 'PhoneCreate'
    statuses: Optional[list['CallStatusDB']] = None


class CallDB(BaseModel):
    """Schema for Call model"""

    id: int
    channel_id: Optional[str]
    phone: 'PhoneDB'
    statuses: list['CallStatusDB']

    model_config = ConfigDict(from_attributes=True)


class CallListDB(BaseModel):
    calls: list[CallDB]


class PhoneCreate(BaseModel):
    """Schema for Phone creating."""
    digits: str


class PhoneDB(BaseModel):
    """Schema for Phone model"""
    digits: str

    model_config = ConfigDict(from_attributes=True)


class CallStatusCreate(BaseModel):
    """Schema for CallStatus creating."""

    status_str: str
    call_id: int


class CallStatusDB(BaseModel):
    """Schema for CallStatus model"""

    status_str: str

    model_config = ConfigDict(from_attributes=True)
