
from bukafit.core.schemas import (
    Goal, Level, Inventory, ProfileData,
    ProgramData, LogData,
)
from bukafit.db import repositories as repo


async def test_get_or_create_user_idempotent(session):
    u1 = await repo.get_or_create_user(session, tg_id=111)
    u2 = await repo.get_or_create_user(session, tg_id=111)
    assert u1.id == u2.id


async def test_save_and_get_profile(session):
    user = await repo.get_or_create_user(session, tg_id=222)
    data = ProfileData(goal=Goal.MASS, level=Level.BEGINNER, inventory=Inventory.GYM, days=[1, 4])
    await repo.save_profile(session, user.id, data)
    got = await repo.get_profile(session, user.id)
    assert got == data


async def test_active_program_replaced(session):
    user = await repo.get_or_create_user(session, tg_id=333)
    p1 = ProgramData(note="v1")
    p2 = ProgramData(note="v2")
    await repo.save_program(session, user.id, p1)
    await repo.save_program(session, user.id, p2)
    active = await repo.get_active_program(session, user.id)
    assert active.note == "v2"


async def test_logs_and_last(session):
    user = await repo.get_or_create_user(session, tg_id=444)
    await repo.add_log(session, user.id, "squat", done=True, data=LogData(weight=40, reps=8, rpe=7))
    await repo.add_log(session, user.id, "squat", done=True, data=LogData(weight=42.5, reps=8, rpe=8))
    last = await repo.last_log(session, user.id, "squat")
    assert last.weight == 42.5
    assert await repo.last_log(session, user.id, "bench") is None


async def test_weekly_count(session):
    user = await repo.get_or_create_user(session, tg_id=555)
    await repo.add_log(session, user.id, "squat", done=True, data=LogData(reps=8))
    await repo.add_log(session, user.id, "bench", done=False, data=LogData(reps=0))
    assert await repo.weekly_done_count(session, user.id) == 1
