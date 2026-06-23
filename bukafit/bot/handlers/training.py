from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.bot import keyboards as kb
from bukafit.core.clock import weekday_local
from bukafit.core.models import User
from bukafit.core.progression import suggest
from bukafit.core.schedule import next_workout, workout_for_today
from bukafit.core.schemas import LogData
from bukafit.db import repositories as repo

router = Router()


def _fmt_w(weight: float | None) -> str:
    return f"{weight} кг" if weight is not None else "свой вес"


async def _card_and_kb(session: AsyncSession, user_id: int, ex):
    last = await repo.last_log(session, user_id, ex.key)
    s = suggest(last, ex)
    text = (
        f"<b>{ex.name}</b>\n"
        f"Цель: {ex.sets}×{s.reps}, {_fmt_w(s.weight)} ({s.note})\n"
        f"Отдых: {ex.rest_sec} сек"
    )
    return text, kb.log_kb(ex.key, s.weight)


@router.message(Command("today"))
async def cmd_today(message: Message, session: AsyncSession, user: User):
    program = await repo.get_active_program(session, user.id)
    if program is None:
        await message.answer("Программы пока нет. Набери /start, соберём её.")
        return

    day = workout_for_today(program, weekday_local())
    if day is None:
        nxt = next_workout(program, weekday_local())
        if nxt:
            await message.answer(
                f"Сегодня день отдыха 😌 Ближайшая тренировка: <b>{nxt.title}</b>."
            )
        else:
            await message.answer("Сегодня отдых 😌")
        return

    await message.answer(f"🏋️ Сегодня: <b>{day.title}</b>")
    for ex in day.exercises:
        text, markup = await _card_and_kb(session, user.id, ex)
        await message.answer(text, reply_markup=markup)


def _find_exercise(program, key):
    for day in program.days:
        for ex in day.exercises:
            if ex.key == key:
                return ex
    return None


@router.callback_query(F.data.startswith("log:"))
async def on_log(cb: CallbackQuery, session: AsyncSession, user: User):
    _, key, action, wstr = cb.data.split(":", 3)
    weight = None if wstr == "none" else float(wstr)

    program = await repo.get_active_program(session, user.id)
    ex = _find_exercise(program, key) if program else None
    if ex is None:
        await cb.answer("Упражнение не найдено", show_alert=True)
        return

    last = await repo.last_log(session, user.id, key)
    reps = suggest(last, ex).reps

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
            f"<b>{ex.name}</b>\nЦель: {ex.sets}×{reps}, {_fmt_w(weight)}",
            reply_markup=kb.log_kb(key, weight),
        )
        await cb.answer("Вес обновлён")
        return

    # action == "done" — log the (possibly adjusted) weight
    await repo.add_log(
        session, user.id, key, done=True,
        data=LogData(weight=weight, reps=reps, rpe=7),
    )
    await cb.message.edit_text(f"✅ {ex.name} — записал: {_fmt_w(weight)} × {reps}")
    await cb.answer("Записал 💪")
