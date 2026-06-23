from bukafit.core.progression import suggest, Suggestion
from bukafit.core.schemas import ExercisePlan, LogData


def plan(weight=40.0, reps=8):
    return ExercisePlan(key="squat", name="Присед", sets=3, target_reps=reps, target_weight=weight)


def test_no_history_uses_plan_targets():
    s = suggest(None, plan())
    assert s == Suggestion(weight=40.0, reps=8, note="по плану")


def test_hit_target_low_rpe_increases_weight():
    last = LogData(weight=40.0, reps=8, rpe=6)
    s = suggest(last, plan())
    assert s.weight == 42.5
    assert s.reps == 8


def test_high_rpe_deloads():
    last = LogData(weight=40.0, reps=8, rpe=9)
    s = suggest(last, plan())
    assert s.weight == 36.0
    assert "сниз" in s.note.lower()


def test_missed_reps_holds():
    last = LogData(weight=40.0, reps=5, rpe=8)
    s = suggest(last, plan())
    assert s.weight == 40.0
    assert s.reps == 8


def test_bodyweight_increases_reps():
    last = LogData(weight=None, reps=10, rpe=6)
    s = suggest(last, plan(weight=None, reps=10))
    assert s.weight is None
    assert s.reps == 11
