from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.core.models import Profile, Program, Summary, User, WorkoutLog
from bukafit.core.schemas import LogData, ProfileData, ProgramData, SummaryData


async def get_or_create_user(session: AsyncSession, tg_id: int) -> User:
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if user is None:
        user = User(tg_id=tg_id)
        session.add(user)
        await session.flush()
    return user


async def get_profile(session: AsyncSession, user_id: int) -> ProfileData | None:
    row = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    return ProfileData.model_validate(row.data) if row else None


async def save_profile(session: AsyncSession, user_id: int, data: ProfileData) -> None:
    row = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    if row is None:
        session.add(Profile(user_id=user_id, data=data.model_dump(mode="json")))
    else:
        row.data = data.model_dump(mode="json")
    await session.flush()


async def get_active_program(session: AsyncSession, user_id: int) -> ProgramData | None:
    row = await session.scalar(
        select(Program).where(Program.user_id == user_id, Program.is_active.is_(True))
    )
    return ProgramData.model_validate(row.data) if row else None


async def save_program(session: AsyncSession, user_id: int, data: ProgramData) -> None:
    await session.execute(
        update(Program).where(Program.user_id == user_id).values(is_active=False)
    )
    session.add(Program(user_id=user_id, is_active=True, data=data.model_dump(mode="json")))
    await session.flush()


async def add_log(
    session: AsyncSession, user_id: int, exercise_key: str, done: bool, data: LogData
) -> None:
    session.add(
        WorkoutLog(
            user_id=user_id,
            exercise_key=exercise_key,
            done=done,
            data=data.model_dump(mode="json"),
        )
    )
    await session.flush()


async def last_log(
    session: AsyncSession, user_id: int, exercise_key: str
) -> LogData | None:
    row = await session.scalar(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == user_id, WorkoutLog.exercise_key == exercise_key)
        .order_by(WorkoutLog.created_at.desc(), WorkoutLog.id.desc())
        .limit(1)
    )
    return LogData.model_validate(row.data) if row else None


async def weekly_done_count(session: AsyncSession, user_id: int) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    rows = await session.scalars(
        select(WorkoutLog).where(
            WorkoutLog.user_id == user_id,
            WorkoutLog.done.is_(True),
            WorkoutLog.created_at >= since,
        )
    )
    return len(rows.all())


async def get_summary(session: AsyncSession, user_id: int) -> SummaryData | None:
    row = await session.scalar(select(Summary).where(Summary.user_id == user_id))
    return SummaryData.model_validate(row.data) if row else None


async def save_summary(session: AsyncSession, user_id: int, data: SummaryData) -> None:
    row = await session.scalar(select(Summary).where(Summary.user_id == user_id))
    if row is None:
        session.add(Summary(user_id=user_id, data=data.model_dump(mode="json")))
    else:
        row.data = data.model_dump(mode="json")
    await session.flush()
