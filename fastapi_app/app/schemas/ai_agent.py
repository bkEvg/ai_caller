from enum import Enum
from typing import Optional

from pydantic import (BaseModel, Field, field_validator, ValidationError,
                      ConfigDict)


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


class PhoneRequest(BaseModel):

    digits: str = Field(..., min_length=11, max_length=15)

    model_config = ConfigDict(
        title="Класс для звонка",
    )

    @field_validator('digits', mode='after')
    @classmethod
    def validate_phone(cls, value: str):
        if not value.startswith('7'):
            raise ValidationError('Номер должен начинаться с 7')

        if not value.isnumeric():
            raise ValidationError('Номер должен состоять только из цифр')
        return value


class BaseResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )


class StatusesResponse(BaseResponse):
    """Schema for CallStatus model"""
    status_str: str


class PhoneResponse(BaseResponse):
    """Schema for Phone model"""
    digits: str


class CallResponse(BaseResponse):
    """Schema for Call model"""

    channel_id: Optional[str]
    phone: PhoneResponse
    statuses: list[StatusesResponse]
