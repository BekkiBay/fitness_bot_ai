import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.db.session import engine, SessionMaker


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """Сессия в транзакции с откатом после теста — чистая изоляция."""
    conn = await engine.connect()
    trans = await conn.begin()
    sess = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield sess
    finally:
        await sess.close()
        await trans.rollback()
        await conn.close()
