from enum import Enum

from pydantic import BaseModel, Field


class Goal(str, Enum):
    MASS = "mass"      # набор массы
    CUT = "cut"        # сушка
    HEALTH = "health"  # здоровье/тонус


class Level(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Inventory(str, Enum):
    GYM = "gym"
    HOME = "home"


class ProfileData(BaseModel):
    goal: Goal
    level: Level
    inventory: Inventory
    days: list[int] = Field(default_factory=list)  # дни недели 1..7 (Пн=1)
    injuries: list[str] = Field(default_factory=list)
    notes: str = ""


class ExercisePlan(BaseModel):
    key: str                       # слаг упражнения, напр. "squat"
    name: str                      # человекочитаемое имя
    sets: int = 3
    target_reps: int = 10
    target_weight: float | None = None  # None = без веса (свой вес)
    rest_sec: int = 90
    alternatives: list[str] = Field(default_factory=list)


class DayPlan(BaseModel):
    weekday: int                   # 1..7 (Пн=1)
    title: str
    exercises: list[ExercisePlan] = Field(default_factory=list)


class ProgramData(BaseModel):
    days: list[DayPlan] = Field(default_factory=list)
    note: str = ""


class LogData(BaseModel):
    weight: float | None = None
    reps: int = 0
    rpe: int = 7                   # 1..10 субъективная нагрузка
    note: str = ""


class SummaryData(BaseModel):
    text: str = ""
