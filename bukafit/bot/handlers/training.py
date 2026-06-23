from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.bot import keyboards as kb
from bukafit.core.models import User
from bukafit.core.progression import suggest
from bukafit.core.schedule import next_workout, workout_for_today
from bukafit.core.schemas import LogData
from bukafit.db import repositories as repo

router = Router()


def _today_weekday() -> int:
    return datetime.now(timezone.utc).isoweekday()  # Пн=1..Вс=7


async def _exercise_card(session: AsyncSession, user_id: int, ex) -> str:
    last = await repo.last_log(session, user_id, ex.key)
    s = suggest(last, ex)
    weight = f"{s.weight} кг" if s.weight is not None else "свой вес"
    return (
        f"<b>{ex.name}</b>\n"
        f"Цель: {ex.sets}×{s.reps}, {weight} ({s.note})\n"
        f"Отдых: {ex.rest_sec} сек"
    )


@router.message(Command("today"))
async def cmd_today(message: Message, session: AsyncSession, user: User):
    program = await repo.get_active_program(session, user.id)
    if program is None:
        await message.answer("Программы пока нет. Набери /start, соберём её.")
        return

    day = workout_for_today(program, _today_weekday())
    if day is None:
        nxt = next_workout(program, _today_weekday())
        if nxt:
            await message.answer(
                f"Сегодня день отдыха 😌 Ближайшая тренировка: <b>{nxt.title}</b>."
            )
        else:
            await message.answer("Сегодня отдых 😌")
        return

    await message.answer(f"🏋️ Сегодня: <b>{day.title}</b>")
    for ex in day.exercises:
        await message.answer(
            await _exercise_card(session, user.id, ex),
            reply_markup=kb.log_kb(ex.key),
        )


def _find_exercise(program, key):
    for day in program.days:
        for ex in day.exercises:
            if ex.key == key:
                return ex
    return None


@router.callback_query(F.data.startswith("log:"))
async def on_log(cb: CallbackQuery, session: AsyncSession, user: User):
    _, key, action = cb.data.split(":")
    program = await repo.get_active_program(session, user.id)
    ex = _find_exercise(program, key) if program else None
    if ex is None:
        await cb.answer("Упражнение не найдено", show_alert=True)
        return

    last = await repo.last_log(session, user.id, key)
    s = suggest(last, ex)
    weight = s.weight

    if action == "skip":
        await repo.add_log(session, user.id, key, done=False, data=LogData(weight=weight, reps=0))
        await cb.message.edit_text(f"⏭️ {ex.name} — пропущено")
        await cb.answer()
        return

    if action == "wup" and weight is not None:
        weight += 2.5
    elif action == "wdown" and weight is not None:
        weight = max(0.0, weight - 2.5)

    if action in ("wup", "wdown"):
        await cb.message.edit_text(
            f"<b>{ex.name}</b>\nЦель: {ex.sets}×{s.reps}, "
            f"{(str(weight) + ' кг') if weight is not None else 'свой вес'}",
            reply_markup=kb.log_kb(key),
        )
        await cb.answer("Вес обновлён")
        return

    await repo.add_log(
        session, user.id, key, done=True,
        data=LogData(weight=weight, reps=s.reps, rpe=7),
    )
    await cb.message.edit_text(
        f"✅ {ex.name} — записал: "
        f"{(str(weight) + ' кг') if weight is not None else 'свой вес'} × {s.reps}"
    )
    await cb.answer("Записал 💪")
