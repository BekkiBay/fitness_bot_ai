from bukafit.core.schemas import (
    Goal, Level, Inventory,
    ProfileData, ExercisePlan, DayPlan, ProgramData, LogData, SummaryData,
)


def test_profile_roundtrip():
    p = ProfileData(
        goal=Goal.MASS, level=Level.BEGINNER, inventory=Inventory.GYM,
        days=[1, 3, 5], injuries=["колено"], notes="без становой",
    )
    dumped = p.model_dump(mode="json")
    restored = ProfileData.model_validate(dumped)
    assert restored == p
    assert restored.goal is Goal.MASS


def test_program_roundtrip():
    prog = ProgramData(
        note="старт",
        days=[
            DayPlan(
                weekday=1, title="Низ тела",
                exercises=[
                    ExercisePlan(
                        key="squat", name="Приседания",
                        sets=3, target_reps=8, target_weight=40.0,
                        rest_sec=120, alternatives=["жим ногами"],
                    )
                ],
            )
        ],
    )
    restored = ProgramData.model_validate(prog.model_dump(mode="json"))
    assert restored.days[0].exercises[0].key == "squat"


def test_log_defaults():
    log = LogData(weight=50.0, reps=8, rpe=7)
    assert log.note == ""


def test_summary():
    s = SummaryData(text="любит присед, прогресс ок")
    assert "присед" in s.text
