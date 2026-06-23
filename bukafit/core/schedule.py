from bukafit.core.schemas import DayPlan, ProgramData


def workout_for_today(program: ProgramData, weekday: int) -> DayPlan | None:
    for day in program.days:
        if day.weekday == weekday:
            return day
    return None


def next_workout(program: ProgramData, weekday: int) -> DayPlan | None:
    if not program.days:
        return None
    ordered = sorted(program.days, key=lambda d: d.weekday)
    for day in ordered:
        if day.weekday > weekday:
            return day
    return ordered[0]
