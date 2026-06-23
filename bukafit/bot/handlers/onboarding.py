from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.ai.provider import ModelProvider
from bukafit.bot import keyboards as kb
from bukafit.core.models import User
from bukafit.core.schemas import Goal, Inventory, Level, ProfileData
from bukafit.db import repositories as repo

router = Router()


class Onboarding(StatesGroup):
    goal = State()
    level = State()
    inventory = State()
    days = State()
    injuries = State()


async def start_onboarding(message: Message, state: FSMContext):
    await state.set_state(Onboarding.goal)
    await message.answer("Какая цель?", reply_markup=kb.goal_kb())


@router.callback_query(Onboarding.goal, F.data.startswith("goal:"))
async def pick_goal(cb: CallbackQuery, state: FSMContext):
    await state.update_data(goal=cb.data.split(":")[1])
    await state.set_state(Onboarding.level)
    await cb.message.edit_text("Твой уровень?", reply_markup=kb.level_kb())
    await cb.answer()


@router.callback_query(Onboarding.level, F.data.startswith("level:"))
async def pick_level(cb: CallbackQuery, state: FSMContext):
    await state.update_data(level=cb.data.split(":")[1])
    await state.set_state(Onboarding.inventory)
    await cb.message.edit_text("Где тренируешься?", reply_markup=kb.inventory_kb())
    await cb.answer()


@router.callback_query(Onboarding.inventory, F.data.startswith("inv:"))
async def pick_inventory(cb: CallbackQuery, state: FSMContext):
    await state.update_data(inventory=cb.data.split(":")[1], days=[])
    await state.set_state(Onboarding.days)
    await cb.message.edit_text(
        "В какие дни недели удобно? Отметь и нажми «Готово».",
        reply_markup=kb.days_kb(set()),
    )
    await cb.answer()


@router.callback_query(Onboarding.days, F.data.startswith("day:"))
async def toggle_day(cb: CallbackQuery, state: FSMContext):
    num = int(cb.data.split(":")[1])
    data = await state.get_data()
    days = set(data.get("days", []))
    days.symmetric_difference_update({num})
    await state.update_data(days=sorted(days))
    await cb.message.edit_reply_markup(reply_markup=kb.days_kb(days))
    await cb.answer()


@router.callback_query(Onboarding.days, F.data == "days:done")
async def days_done(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("days"):
        await cb.answer("Выбери хотя бы один день", show_alert=True)
        return
    await state.set_state(Onboarding.injuries)
    await cb.message.edit_text(
        "Есть травмы или ограничения? Напиши коротко (или нажми кнопку).",
        reply_markup=kb.skip_injuries_kb(),
    )
    await cb.answer()


@router.callback_query(Onboarding.injuries, F.data == "injuries:none")
async def injuries_none(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User,
    provider: ModelProvider,
):
    await _finish(cb.message, state, session, user, provider, injuries=[])
    await cb.answer()


@router.message(Onboarding.injuries, F.text)
async def injuries_text(
    message: Message, state: FSMContext, session: AsyncSession, user: User,
    provider: ModelProvider,
):
    injuries = [s.strip() for s in message.text.split(",") if s.strip()]
    await _finish(message, state, session, user, provider, injuries=injuries)


async def _finish(message, state, session, user, provider, injuries):
    data = await state.get_data()
    profile = ProfileData(
        goal=Goal(data["goal"]),
        level=Level(data["level"]),
        inventory=Inventory(data["inventory"]),
        days=data["days"],
        injuries=injuries,
    )
    await repo.save_profile(session, user.id, profile)
    await state.clear()

    await message.answer("Собираю программу под тебя… ⏳")
    program = await provider.generate_plan(profile)
    await repo.save_program(session, user.id, program)

    lines = [f"Готово! Твоя программа ({len(program.days)} дн./нед.):", ""]
    for day in sorted(program.days, key=lambda d: d.weekday):
        lines.append(f"• {day.title}: " + ", ".join(ex.name for ex in day.exercises))
    lines += ["", "Команда /today покажет тренировку на сегодня. Погнали! 💪"]
    await message.answer("\n".join(lines))
