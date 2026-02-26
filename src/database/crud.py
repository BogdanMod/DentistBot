from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import User, Reminder, RescheduleRequest, NotificationLog


# Класс UserCRUD

class UserCRUD:
    @staticmethod
    async def get_by_chat_id(session: AsyncSession, chat_id: int) -> Optional[User]:
        result = await session.execute(
            select(User).where(User.chat_id == chat_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_by_phone(session: AsyncSession, phone: str) -> Optional[User]:
        result = await session.execute(
            select(User).where(User.phone == phone)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create(
        session: AsyncSession,
        chat_id: int,
        phone: str,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        yclients_client_id: Optional[int] = None,
    ) -> User:
        user = User(
            chat_id=chat_id,
            phone=phone,
            full_name=full_name,
            email=email,
            yclients_client_id=yclients_client_id,
            is_registered=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user
    
    @staticmethod
    async def get_by_yclients_client_id(
        session: AsyncSession,
        yclients_client_id: int
    ) -> Optional[User]:
        """Получить пользователя по YClients client ID"""
        result = await session.execute(
            select(User).where(User.yclients_client_id == yclients_client_id)
        )
        return result.scalar_one_or_none()
        
    
# Класс ReminderCRUD

class ReminderCRUD:
    @staticmethod
    async def get_by_record_id(session: AsyncSession, record_id: int) -> Optional[Reminder]:
        result = await session.execute(
            select(Reminder).where(Reminder.record_id == record_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create(
        session: AsyncSession,
        user_chat_id: int,
        record_id: int,
        appointment_datetime: datetime,
        service_name: str,
        staff_name: str,
        salon_address: Optional[str] = None,
    ) -> Reminder:
        
        reminder = Reminder(
            user_chat_id=user_chat_id,
            record_id=record_id,
            appointment_datetime=appointment_datetime,
            service_name=service_name,
            staff_name=staff_name,
            salon_address=salon_address,
        )
        session.add(reminder)
        await session.commit()
        await session.refresh(reminder)
        return reminder
    
    @staticmethod
    async def mark_as_sent(session: AsyncSession, record_id: int) -> None:
        await session.execute(
            update(Reminder)
            .where(Reminder.record_id == record_id)
            .values(is_sent=True, reminder_sent_at=datetime.utcnow())
        )
        await session.commit()
        
    @staticmethod
    async def mark_as_confirmed(session: AsyncSession, record_id: int) -> None:
        await session.execute(
            update(Reminder)
            .where(Reminder.record_id == record_id)
            .values(is_confirmed=True)
        )
        await session.commit()

    @staticmethod
    async def mark_as_cancelled(session: AsyncSession, record_id: int) -> None:
        await session.execute(
            update(Reminder)
            .where(Reminder.record_id == record_id)
            .values(is_cancelled=True)
        )
        await session.commit()

    @staticmethod
    async def get_unsent_reminders(session: AsyncSession, before_datetime: datetime):
        result = await session.execute(
            select(Reminder)
            .where(
                Reminder.is_sent == False,
                Reminder.appointment_datetime <= before_datetime,
                Reminder.is_cancelled == False
            )
        )
        return list(result.scalars().all())


# Класс RescheduleRequestCRUD

class RescheduleRequestCRUD:
    @staticmethod
    async def create(
        session: AsyncSession,
        record_id: int,
        user_chat_id: int,
        original_datetime: datetime,
        client_phone: str,
        client_name: str,
        service_name: str,
        manager_comment: Optional[str] = None,
    ) -> RescheduleRequest:
        request = RescheduleRequest(
            record_id=record_id,
            user_chat_id=user_chat_id,
            original_datetime=original_datetime,
            client_phone=client_phone,
            client_name=client_name,
            service_name=service_name,
            manager_comment=manager_comment,
            status="pending",
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)
        return request

    @staticmethod
    async def get_pending_requests(session: AsyncSession) -> list[RescheduleRequest]:
        result = await session.execute(
            select(RescheduleRequest).where(RescheduleRequest.status == "pending")
        )
        return list(result.scalars().all())

    @staticmethod
    async def mark_as_processed(
        session: AsyncSession,
        request_id: int,
        manager_comment: Optional[str] = None,
    ) -> None:
        await session.execute(
            update(RescheduleRequest)
            .where(RescheduleRequest.id == request_id)
            .values(
                status="processed",
                processed_at=datetime.utcnow(),
                manager_comment=manager_comment,
            )
        )
        await session.commit()


# Класс NotificationLogCRUD

class NotificationLogCRUD:
    @staticmethod
    async def log_notification(
        session: AsyncSession,
        chat_id: int,
        message_type: str,
        record_id: Optional[int] = None,
        is_successful: bool = True,
        error_message: Optional[str] = None,
    ) -> NotificationLog:
        log_entry = NotificationLog(
            chat_id=chat_id,
            message_type=message_type,
            record_id=record_id,
            is_successful=is_successful,
            error_message=error_message,
        )
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)
        return log_entry