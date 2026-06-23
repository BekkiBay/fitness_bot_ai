
from bukafit.ai.codex import CodexProvider, extract_json
from bukafit.ai.provider import Memory
from bukafit.core.schemas import (
    Goal, Level, Inventory, ProfileData, ProgramData, DayPlan,
)


def test_extract_json_from_fenced():
    raw = "болтовня\n```json\n{\"a\": 1}\n```\nхвост"
    assert extract_json(raw) == {"a": 1}


def test_extract_json_raw_object():
    raw = "тут {\"b\": 2} внутри текста"
    assert extract_json(raw) == {"b": 2}


async def test_generate_plan_parses(monkeypatch):
    prog = ProgramData(note="ок", days=[DayPlan(weekday=1, title="День", exercises=[])])
    payload = prog.model_dump_json()

    async def fake_run(self, prompt: str) -> str:
        return f"вот план:\n```json\n{payload}\n```"

    monkeypatch.setattr(CodexProvider, "_run", fake_run)
    profile = ProfileData(goal=Goal.MASS, level=Level.BEGINNER, inventory=Inventory.GYM, days=[1])
    out = await CodexProvider().generate_plan(profile)
    assert out.days[0].title == "День"


async def test_generate_plan_fallback_on_garbage(monkeypatch):
    async def fake_run(self, prompt: str) -> str:
        return "никакого json тут нет"

    monkeypatch.setattr(CodexProvider, "_run", fake_run)
    profile = ProfileData(goal=Goal.MASS, level=Level.BEGINNER, inventory=Inventory.GYM, days=[1, 5])
    out = await CodexProvider().generate_plan(profile)
    assert {d.weekday for d in out.days} == {1, 5}


async def test_answer_question_passthrough(monkeypatch):
    async def fake_run(self, prompt: str) -> str:
        return "  делай так и так  "

    monkeypatch.setattr(CodexProvider, "_run", fake_run)
    ans = await CodexProvider().answer_question("вопрос", Memory())
    assert ans == "делай так и так"
