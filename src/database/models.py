from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Базовый класс
class Base(DeclarativeBase):
    pass


# Модель User
class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yclients_client_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    
# Модель Reminder
class Reminder(Base):
    
    __tablename__ = "reminders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    record_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    appointment_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    service_name: Mapped[str] = mapped_column(String(255))
    staff_name: Mapped[str] = mapped_column(String(255))
    salon_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    
 # Модель RescheduleRequest
 
class RescheduleRequest(Base):
    __tablename__ = "reschedule_requests"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(Integer, index=True)
    user_chat_id: Mapped[int] = mapped_column(BigInteger)
    original_datetime: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    client_phone: Mapped[str] = mapped_column(String(20))
    client_name: Mapped[str] = mapped_column(String(255))
    service_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    manager_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    
# Модель NotificationLog

class NotificationLog(Base):
    __tablename__ = "notification_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    message_type: Mapped[str] = mapped_column(String(50))
    record_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_successful: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())