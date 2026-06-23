from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.bot.handlers.onboarding import start_onboarding
from bukafit.core.models import User, WorkoutLog
from bukafit.core.streaks import current_streak
from bukafit.db import repositories as repo

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession, user: User, state: FSMContext):
    profile = await repo.get_profile(session, user.id)
    if profile is None:
        await message.answer(
            "Привет! Я тренер BukaFit 💪 Помогу собрать программу и вести тренировки.\n"
            "Давай за минуту настроимся."
        )
        await start_onboarding(message, state)
        return
    await message.answer(
        "С возвращением! 👋\n"
        "/today — тренировка на сегодня\n"
        "/progress — твой прогресс\n"
        "Или просто напиши вопрос про тренировки и питание."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Что я умею:\n"
        "/today — план на сегодня и отметка тренировки\n"
        "/progress — серия и активность за неделю\n"
        "/start — пройти настройку заново\n\n"
        "Ещё можешь спросить меня про технику, замену упражнения или питание."
    )


@router.message(Command("progress"))
async def cmd_progress(message: Message, session: AsyncSession, user: User):
    week = await repo.weekly_done_count(session, user.id)
    rows = await session.scalars(
        select(WorkoutLog.created_at).where(
            WorkoutLog.user_id == user.id, WorkoutLog.done.is_(True)
        )
    )
    dates = [d.astimezone(timezone.utc).date() for d in rows.all()]
    streak = current_streak(dates, today=datetime.now(timezone.utc).date())
    await message.answer(
        f"📊 Твой прогресс:\n"
        f"• Тренировок за неделю: {week}\n"
        f"• Серия подряд: {streak} дн.\n\n"
        + ("Так держать! 🔥" if week >= 2 else "Давай хотя бы 2 тренировки на неделе 💪")
    )
