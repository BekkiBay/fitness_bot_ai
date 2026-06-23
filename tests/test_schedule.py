from bukafit.core.schedule import workout_for_today, next_workout
from bukafit.core.schemas import ProgramData, DayPlan


def prog():
    return ProgramData(days=[
        DayPlan(weekday=1, title="Низ"),
        DayPlan(weekday=3, title="Верх"),
        DayPlan(weekday=5, title="Всё тело"),
    ])


def test_today_match():
    d = workout_for_today(prog(), weekday=3)
    assert d.title == "Верх"


def test_today_none_on_rest_day():
    assert workout_for_today(prog(), weekday=2) is None


def test_next_from_rest_day():
    d = next_workout(prog(), weekday=2)
    assert d.title == "Верх"


def test_next_wraps_around_week():
    d = next_workout(prog(), weekday=6)
    assert d.title == "Низ"


def test_next_empty_program():
    assert next_workout(ProgramData(), weekday=1) is None
