from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, ForeignKey, Text

from app.core.db import Base

MAX_CHANNEL_LENGTH = 50
MAX_UUID_LENGTH = 50
MAX_STATUS_LENGTH = 100
MAX_PHONE_LENGTH = 20


class Dialog(Base):
    """Model of Dialog between users."""
    call_id: Mapped[int] = mapped_column(ForeignKey('call.id'), unique=True)
    call: Mapped['Call'] = relationship(back_populates='dialog', uselist=False)
    phrases: Mapped[list['Phrase']] = relationship(
        back_populates='dialog', cascade='all, delete-orphan')


class Phrase(Base):
    """Model of user's phrases."""

    dialog_id: Mapped[int] = mapped_column(ForeignKey('dialog.id'))
    dialog: Mapped[Dialog] = relationship(back_populates='phrases')
    content: Mapped[str] = mapped_column(Text, nullable=True)


class Phone(Base):
    """Phone model object."""
    digits: Mapped[str] = mapped_column(String(MAX_PHONE_LENGTH), unique=True)
    calls: Mapped[list['Call']] = relationship(
        back_populates='phone', cascade='all, delete-orphan')


class CallStatus(Base):
    """Call Status model object."""

    status_str: Mapped[str] = mapped_column(String(MAX_STATUS_LENGTH))
    call_id: Mapped[int] = mapped_column(ForeignKey('call.id'))
    call: Mapped['Call'] = relationship(back_populates='statuses')


class Call(Base):
    """Call model object."""

    channel_id: Mapped[str] = mapped_column(
        String(MAX_CHANNEL_LENGTH), unique=True, nullable=True)
    uuid: Mapped[str] = mapped_column(String(MAX_UUID_LENGTH), unique=True)
    status: Mapped[str] = mapped_column(String(MAX_STATUS_LENGTH))

    # Relationships
    phone_id: Mapped[int] = mapped_column(ForeignKey('phone.id'))
    phone: Mapped[Phone] = relationship(back_populates='calls')
    dialog: Mapped[Dialog] = relationship(back_populates='call',
                                          cascade='all, delete-orphan')
    statuses: Mapped[list[CallStatus]] = relationship(
        back_populates='call', cascade='all, delete-orphan',
        order_by='CallStatus.created_at')
