from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from src.config import settings
from src.database.models import Base


#Класс DatabaseManager

class DatabaseManager:
    def __init__(self, database_url: str):
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            echo=True,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def init_db(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self) -> None:
        await self.engine.dispose()

db_manager = DatabaseManager(settings.DATABASE_URL)