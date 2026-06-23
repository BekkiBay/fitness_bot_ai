from bukafit.ai.memory import build_memory
from bukafit.core.schemas import (
    Goal, Level, Inventory, ProfileData, ProgramData, DayPlan, ExercisePlan, LogData, SummaryData,
)
from bukafit.db import repositories as repo


async def test_build_memory_collects_everything(session):
    user = await repo.get_or_create_user(session, tg_id=9001)
    await repo.save_profile(
        session, user.id,
        ProfileData(goal=Goal.MASS, level=Level.BEGINNER, inventory=Inventory.GYM, days=[1]),
    )
    await repo.save_program(session, user.id, ProgramData(days=[
        DayPlan(weekday=1, title="День", exercises=[
            ExercisePlan(key="squat", name="Приседания", target_weight=40, target_reps=8),
        ]),
    ]))
    await repo.add_log(session, user.id, "squat", done=True, data=LogData(weight=40, reps=8, rpe=7))
    await repo.save_summary(session, user.id, SummaryData(text="любит присед"))

    mem = await build_memory(session, user.id)
    assert mem.profile is not None and mem.profile.goal is Goal.MASS
    assert mem.program is not None
    assert any("Приседания" in r for r in mem.recent)
    assert mem.summary == "любит присед"


async def test_build_memory_empty_user(session):
    user = await repo.get_or_create_user(session, tg_id=9002)
    mem = await build_memory(session, user.id)
    assert mem.profile is None
    assert mem.program is None
    assert mem.recent == []
    assert mem.summary == ""
