from dataclasses import dataclass

from bukafit.core.schemas import ExercisePlan, LogData

WEIGHT_STEP = 2.5      # шаг увеличения веса, кг
DELOAD_FACTOR = 0.9    # делоуд -10%
EASY_RPE = 7           # <= считаем лёгким
HARD_RPE = 9           # >= считаем тяжёлым


def _round_half(x: float) -> float:
    return round(x * 2) / 2


@dataclass(frozen=True)
class Suggestion:
    weight: float | None
    reps: int
    note: str


def suggest(last: LogData | None, plan: ExercisePlan) -> Suggestion:
    if last is None:
        return Suggestion(weight=plan.target_weight, reps=plan.target_reps, note="по плану")

    hit_target = last.reps >= plan.target_reps

    if last.rpe >= HARD_RPE:
        if plan.target_weight is not None and last.weight is not None:
            return Suggestion(
                weight=_round_half(last.weight * DELOAD_FACTOR),
                reps=plan.target_reps,
                note="было тяжело — снизим вес",
            )
        return Suggestion(weight=None, reps=plan.target_reps, note="было тяжело — держим")

    if hit_target and last.rpe <= EASY_RPE:
        if plan.target_weight is not None and last.weight is not None:
            return Suggestion(
                weight=_round_half(last.weight + WEIGHT_STEP),
                reps=plan.target_reps,
                note="идём вверх по весу",
            )
        return Suggestion(weight=None, reps=last.reps + 1, note="добавим повтор")

    base_weight = last.weight if last.weight is not None else plan.target_weight
    return Suggestion(weight=base_weight, reps=plan.target_reps, note="закрепляем")
