from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bukafit.core.schemas import Goal, Inventory, Level

WEEKDAYS = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Вс"}


def goal_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💪 Набор массы", callback_data=f"goal:{Goal.MASS.value}")
    b.button(text="🔥 Сушка", callback_data=f"goal:{Goal.CUT.value}")
    b.button(text="🧘 Здоровье", callback_data=f"goal:{Goal.HEALTH.value}")
    b.adjust(1)
    return b.as_markup()


def level_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🌱 Новичок", callback_data=f"level:{Level.BEGINNER.value}")
    b.button(text="⚙️ Средний", callback_data=f"level:{Level.INTERMEDIATE.value}")
    b.button(text="🏆 Опытный", callback_data=f"level:{Level.ADVANCED.value}")
    b.adjust(1)
    return b.as_markup()


def inventory_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏋️ Зал", callback_data=f"inv:{Inventory.GYM.value}")
    b.button(text="🏠 Дом", callback_data=f"inv:{Inventory.HOME.value}")
    b.adjust(2)
    return b.as_markup()


def days_kb(selected: set[int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for num, name in WEEKDAYS.items():
        mark = "✅ " if num in selected else ""
        b.button(text=f"{mark}{name}", callback_data=f"day:{num}")
    b.button(text="Готово ▶️", callback_data="days:done")
    b.adjust(4, 3, 1)
    return b.as_markup()


def skip_injuries_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Нет ограничений ▶️", callback_data="injuries:none")
    return b.as_markup()


def log_kb(exercise_key: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Сделал", callback_data=f"log:{exercise_key}:done")
    b.button(text="➖ вес", callback_data=f"log:{exercise_key}:wdown")
    b.button(text="➕ вес", callback_data=f"log:{exercise_key}:wup")
    b.button(text="⏭️ Пропустить", callback_data=f"log:{exercise_key}:skip")
    b.adjust(1, 2, 1)
    return b.as_markup()
