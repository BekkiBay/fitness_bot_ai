from bukafit.ai.mock import MockProvider
from bukafit.ai.provider import Memory
from bukafit.ai import prompts
from bukafit.core.schemas import Goal, Level, Inventory, ProfileData


def gym_profile(days):
    return ProfileData(goal=Goal.MASS, level=Level.BEGINNER, inventory=Inventory.GYM, days=days)


async def test_plan_has_day_per_schedule():
    prog = await MockProvider().generate_plan(gym_profile([1, 3, 5]))
    assert {d.weekday for d in prog.days} == {1, 3, 5}
    assert all(d.exercises for d in prog.days)


async def test_gym_has_weighted_exercises():
    prog = await MockProvider().generate_plan(gym_profile([1]))
    assert any(ex.target_weight is not None for ex in prog.days[0].exercises)


async def test_home_is_bodyweight():
    profile = ProfileData(goal=Goal.HEALTH, level=Level.BEGINNER, inventory=Inventory.HOME, days=[2])
    prog = await MockProvider().generate_plan(profile)
    assert all(ex.target_weight is None for ex in prog.days[0].exercises)


async def test_answer_includes_disclaimer():
    ans = await MockProvider().answer_question("как присед?", Memory())
    assert prompts.DISCLAIMER in ans
