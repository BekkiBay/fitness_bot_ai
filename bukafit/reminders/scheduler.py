import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from bukafit.config import settings
from bukafit.core.models import User
from bukafit.core.schedule import workout_for_today
from bukafit.db import repositories as repo
from bukafit.db.session import SessionMaker

log = logging.getLogger(__name__)


def _today_weekday() -> int:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoweekday()


async def morning_plan(bot: Bot) -> None:
    async with SessionMaker() as session:
        users = (await session.scalars(select(User))).all()
        wd = _today_weekday()
        for user in users:
            program = await repo.get_active_program(session, user.id)
            if not program:
                continue
            day = workout_for_today(program, wd)
            text = (
                f"☀️ Доброе утро! Сегодня: <b>{day.title}</b>. Набери /today."
                if day else "☀️ Доброе утро! Сегодня день отдыха — восстанавливайся 😌"
            )
            try:
                await bot.send_message(user.tg_id, text)
            except Exception as e:  # noqa: BLE001
                log.warning("morning send failed for %s: %s", user.tg_id, e)


async def evening_check(bot: Bot) -> None:
    async with SessionMaker() as session:
        users = (await session.scalars(select(User))).all()
        for user in users:
            done = await repo.weekly_done_count(session, user.id)
            try:
                await bot.send_message(
                    user.tg_id,
                    f"🌙 Итог дня. Тренировок за неделю: {done}. "
                    + ("Красава! 🔥" if done >= 2 else "Завтра наверстаем 💪"),
                )
            except Exception as e:  # noqa: BLE001
                log.warning("evening send failed for %s: %s", user.tg_id, e)


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(morning_plan, "cron", hour=8, minute=0, args=[bot])
    scheduler.add_job(evening_check, "cron", hour=21, minute=0, args=[bot])
    scheduler.start()
    return scheduler
