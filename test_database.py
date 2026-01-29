import asyncio
from datetime import datetime
from src.database.database import db_manager
from src.database.crud import UserCRUD, ReminderCRUD

async def test():
    await db_manager.init_db()
    
    async for session in db_manager.get_session():
        user = await UserCRUD.create(
            session=session,
            chat_id=123456789,
            phone="+79001234567",
            full_name="Test User"
        )
        print(f"Created user ID: {user.id}")
        
        found = await UserCRUD.get_by_chat_id(session, 123456789)
        print(f"Found user: {found.full_name}")
        
        reminder = await ReminderCRUD.create(
            session=session,
            user_chat_id=123456789,
            record_id=999,
            appointment_datetime=datetime.now(),
            service_name="Test Service",
            staff_name="Test Staff"
        )
        print(f"Created reminder ID: {reminder.id}")

if __name__ == "__main__":
    asyncio.run(test())