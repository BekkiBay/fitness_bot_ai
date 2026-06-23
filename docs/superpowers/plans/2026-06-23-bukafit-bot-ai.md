# BukaFit — План 2: Бот, ИИ-слой, напоминания

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Поверх готового ядра (План 1) собрать рабочего Telegram-бота: слой моделей (Mock + Codex через OAuth), компактную память, онбординг, логирование тренировок с прогрессией, чат-вопросы и напоминания.

**Architecture:** aiogram 3 (роутеры по фичам), FSM-онбординг в Redis. ИИ за `ModelProvider`-протоколом: `MockProvider` (детерминированный, по умолчанию) и `CodexProvider` (подпроцесс `codex exec` через OAuth). Провайдер и фабрика сессий БД инжектятся в хендлеры через workflow-data и middleware. Память собирается из профиля + состояния тренировок + rolling summary, без сырых диалогов.

**Tech Stack:** aiogram 3, Redis (FSM-хранилище), asyncio subprocess (Codex CLI), APScheduler. Опирается на План 1 (schemas, models, repositories, progression, schedule).

**Предусловие:** План 1 выполнен (`pytest -q` зелёный, миграции применены, БД+Redis в Docker подняты). Для `AI_PROVIDER=codex` нужен установленный `codex` и выполненный `codex login`; по умолчанию `AI_PROVIDER=mock` — бот работает без этого.

---

## Структура файлов (создаётся этим планом)

```
bukafit/
  ai/
    __init__.py
    provider.py        # Protocol ModelProvider + dataclass Memory
    prompts.py         # персона, дисклеймер, шаблоны промптов
    mock.py            # MockProvider — детерминированный план/ответы
    codex.py           # CodexProvider — codex exec через OAuth
    factory.py         # get_provider() по config.ai_provider
    memory.py          # build_memory(session, user_id) -> Memory
  bot/
    __init__.py
    keyboards.py       # inline-клавиатуры
    middleware.py      # DBMiddleware: сессия + user в data
    handlers/
      __init__.py
      common.py        # /start /help /progress
      onboarding.py    # FSM-онбординг
      training.py      # «сегодня» + логирование
      chat.py          # свободный текст -> ИИ
    main.py            # сборка Dispatcher, запуск polling/webhook
  reminders/
    __init__.py
    scheduler.py       # APScheduler: утро/вечер
tests/
  test_mock_provider.py
  test_codex_provider.py
  test_provider_factory.py
  test_memory.py
  test_keyboards.py
```

---

## Task 1: Протокол провайдера + Memory

**Files:**
- Create: `bukafit/ai/__init__.py` (пустой), `bukafit/ai/provider.py`

- [ ] **Step 1: Создать `bukafit/ai/__init__.py`** (пустой файл)

- [ ] **Step 2: Реализовать `bukafit/ai/provider.py`**

```python
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from bukafit.core.schemas import ProfileData, ProgramData


@dataclass
class Memory:
    """Компактный контекст для ответа ИИ — без сырых диалогов."""
    profile: ProfileData | None = None
    program: ProgramData | None = None
    recent: list[str] = field(default_factory=list)  # последние веса/повторы
    summary: str = ""                                  # rolling summary


@runtime_checkable
class ModelProvider(Protocol):
    async def generate_plan(self, profile: ProfileData) -> ProgramData: ...
    async def answer_question(self, question: str, memory: Memory) -> str: ...
```

- [ ] **Step 3: Проверить импорт**

Run: `. .venv/bin/activate && python -c "from bukafit.ai.provider import Memory, ModelProvider; print('ok', Memory())"`
Expected: `ok Memory(profile=None, program=None, recent=[], summary='')`

- [ ] **Step 4: Commit**

```bash
git add bukafit/ai/__init__.py bukafit/ai/provider.py
git commit -m "feat: ModelProvider protocol + Memory dataclass"
```

---

## Task 2: Промпты (персона, дисклеймер, шаблоны)

**Files:**
- Create: `bukafit/ai/prompts.py`

- [ ] **Step 1: Реализовать `bukafit/ai/prompts.py`**

```python
from bukafit.ai.provider import Memory
from bukafit.core.schemas import ProfileData

DISCLAIMER = (
    "⚠️ Это общие рекомендации, а не медицинский совет. "
    "При боли, травме или сомнениях — остановись и обратись к врачу или тренеру."
)

# Тон задаётся промптом, не моделью (BukaFit.md §8).
SYSTEM_PERSONA = """\
Ты — тренер фитнес-зала BukaFit. Говоришь как живой человек: коротко, по делу, \
дружелюбно и на «ты». Русский язык, разговорный, без канцелярита.

Запрещено:
- клише ИИ: «как языковая модель», «важно отметить», «в заключение», «в современном мире»;
- длинные вступления и извинения;
- медицинские диагнозы и опасные советы (тяжёлые травмы → к врачу/тренеру).

Отвечай по сути вопроса. Если не уверен — честно скажи и предложи спросить тренера.
"""

PLAN_JSON_INSTRUCTION = """\
Верни ТОЛЬКО валидный JSON по схеме (без пояснений, без markdown-обёртки):
{
  "note": "короткий комментарий к программе",
  "days": [
    {
      "weekday": 1,
      "title": "название дня",
      "exercises": [
        {"key": "squat", "name": "Приседания", "sets": 3, "target_reps": 8,
         "target_weight": 40.0, "rest_sec": 120, "alternatives": ["жим ногами"]}
      ]
    }
  ]
}
Правила: weekday — числа из графика пользователя (Пн=1..Вс=7). key — латиницей-слаг. \
Для домашних упражнений без веса target_weight = null. Подбирай нагрузку под уровень и цель.
"""


def plan_prompt(profile: ProfileData) -> str:
    return (
        f"{SYSTEM_PERSONA}\n\n"
        f"Составь недельную программу тренировок.\n"
        f"Цель: {profile.goal.value}. Уровень: {profile.level.value}. "
        f"Инвентарь: {profile.inventory.value}. Дни недели: {profile.days}. "
        f"Травмы/ограничения: {', '.join(profile.injuries) or 'нет'}. "
        f"Заметки: {profile.notes or 'нет'}.\n\n"
        f"{PLAN_JSON_INSTRUCTION}"
    )


def qa_prompt(question: str, memory: Memory) -> str:
    ctx_lines = []
    if memory.profile:
        ctx_lines.append(
            f"Профиль: цель {memory.profile.goal.value}, уровень "
            f"{memory.profile.level.value}, инвентарь {memory.profile.inventory.value}."
        )
    if memory.recent:
        ctx_lines.append("Последние результаты: " + "; ".join(memory.recent[:10]))
    if memory.summary:
        ctx_lines.append(f"Контекст: {memory.summary}")
    ctx = "\n".join(ctx_lines) or "Контекста по пользователю пока нет."

    return (
        f"{SYSTEM_PERSONA}\n\n"
        f"Что известно о пользователе:\n{ctx}\n\n"
        f"Вопрос пользователя: {question}\n\n"
        f"Ответь коротко и по делу."
    )
```

- [ ] **Step 2: Проверить импорт**

Run: `. .venv/bin/activate && python -c "from bukafit.ai import prompts; print(bool(prompts.DISCLAIMER))"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add bukafit/ai/prompts.py
git commit -m "feat: AI prompts (persona, disclaimer, plan/qa templates)"
```

---

## Task 3: MockProvider

**Files:**
- Create: `bukafit/ai/mock.py`
- Test: `tests/test_mock_provider.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_mock_provider.py
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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_mock_provider.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.ai.mock'`

- [ ] **Step 3: Реализовать `bukafit/ai/mock.py`**

```python
from bukafit.ai import prompts
from bukafit.ai.provider import Memory
from bukafit.core.schemas import (
    DayPlan, ExercisePlan, Inventory, ProfileData, ProgramData,
)

WEEKDAY_TITLES = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг",
                  5: "Пятница", 6: "Суббота", 7: "Воскресенье"}

# Шаблоны дней: чередуем низ/верх/всё тело
GYM_TEMPLATES = [
    ("Низ тела", [
        ExercisePlan(key="squat", name="Приседания со штангой", sets=3, target_reps=8,
                     target_weight=40.0, rest_sec=120, alternatives=["жим ногами"]),
        ExercisePlan(key="leg_curl", name="Сгибание ног", sets=3, target_reps=12,
                     target_weight=20.0, rest_sec=90, alternatives=["румынская тяга"]),
        ExercisePlan(key="calf_raise", name="Подъём на носки", sets=3, target_reps=15,
                     target_weight=30.0, rest_sec=60, alternatives=[]),
    ]),
    ("Верх тела", [
        ExercisePlan(key="bench", name="Жим лёжа", sets=3, target_reps=8,
                     target_weight=30.0, rest_sec=120, alternatives=["отжимания"]),
        ExercisePlan(key="row", name="Тяга в наклоне", sets=3, target_reps=10,
                     target_weight=30.0, rest_sec=90, alternatives=["тяга верхнего блока"]),
        ExercisePlan(key="ohp", name="Жим стоя", sets=3, target_reps=10,
                     target_weight=20.0, rest_sec=90, alternatives=["жим гантелей сидя"]),
    ]),
    ("Всё тело", [
        ExercisePlan(key="deadlift", name="Становая тяга", sets=3, target_reps=6,
                     target_weight=50.0, rest_sec=150, alternatives=["гиперэкстензия"]),
        ExercisePlan(key="pulldown", name="Тяга верхнего блока", sets=3, target_reps=10,
                     target_weight=35.0, rest_sec=90, alternatives=["подтягивания"]),
        ExercisePlan(key="plank", name="Планка", sets=3, target_reps=1,
                     target_weight=None, rest_sec=60, alternatives=[]),
    ]),
]

HOME_TEMPLATES = [
    ("Низ тела (дом)", [
        ExercisePlan(key="bw_squat", name="Приседания", sets=3, target_reps=15,
                     target_weight=None, rest_sec=60, alternatives=["выпады"]),
        ExercisePlan(key="lunge", name="Выпады", sets=3, target_reps=12,
                     target_weight=None, rest_sec=60, alternatives=["зашагивания"]),
        ExercisePlan(key="glute_bridge", name="Ягодичный мостик", sets=3, target_reps=15,
                     target_weight=None, rest_sec=60, alternatives=[]),
    ]),
    ("Верх тела (дом)", [
        ExercisePlan(key="pushup", name="Отжимания", sets=3, target_reps=12,
                     target_weight=None, rest_sec=60, alternatives=["отжимания с колен"]),
        ExercisePlan(key="pike_pushup", name="Отжимания уголком", sets=3, target_reps=8,
                     target_weight=None, rest_sec=60, alternatives=[]),
        ExercisePlan(key="superman", name="Лодочка", sets=3, target_reps=15,
                     target_weight=None, rest_sec=45, alternatives=[]),
    ]),
    ("Всё тело (дом)", [
        ExercisePlan(key="burpee", name="Бёрпи", sets=3, target_reps=10,
                     target_weight=None, rest_sec=75, alternatives=["прыжки"]),
        ExercisePlan(key="plank", name="Планка", sets=3, target_reps=1,
                     target_weight=None, rest_sec=60, alternatives=[]),
        ExercisePlan(key="mountain_climber", name="Скалолаз", sets=3, target_reps=20,
                     target_weight=None, rest_sec=45, alternatives=[]),
    ]),
]


class MockProvider:
    """Детерминированный провайдер: реальный ИИ не нужен."""

    async def generate_plan(self, profile: ProfileData) -> ProgramData:
        templates = HOME_TEMPLATES if profile.inventory is Inventory.HOME else GYM_TEMPLATES
        days = profile.days or [1, 3, 5]
        result = []
        for i, wd in enumerate(sorted(days)):
            base_title, exercises = templates[i % len(templates)]
            result.append(DayPlan(
                weekday=wd,
                title=f"{base_title} · {WEEKDAY_TITLES.get(wd, '')}".strip(" ·"),
                exercises=[ex.model_copy(deep=True) for ex in exercises],
            ))
        return ProgramData(note="Стартовая программа BukaFit", days=result)

    async def answer_question(self, question: str, memory: Memory) -> str:
        body = (
            "Коротко: держи технику чисто, не гонись за весом, "
            "добавляй нагрузку постепенно. Если вопрос про конкретное упражнение — "
            "следи за нейтральной спиной и полной амплитудой."
        )
        return f"{body}\n\n{prompts.DISCLAIMER}"
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/test_mock_provider.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add bukafit/ai/mock.py tests/test_mock_provider.py
git commit -m "feat: MockProvider (deterministic plan + canned answers)"
```

---

## Task 4: CodexProvider (codex exec через OAuth)

**Files:**
- Create: `bukafit/ai/codex.py`
- Test: `tests/test_codex_provider.py`

> Тест мокает `_run` (запуск CLI), чтобы не требовать установленный `codex`. Проверяется логика извлечения/валидации JSON и проброс текста.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_codex_provider.py
import pytest

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
    # упал на mock-фоллбэк → план под расписание построен
    assert {d.weekday for d in out.days} == {1, 5}


async def test_answer_question_passthrough(monkeypatch):
    async def fake_run(self, prompt: str) -> str:
        return "  делай так и так  "

    monkeypatch.setattr(CodexProvider, "_run", fake_run)
    ans = await CodexProvider().answer_question("вопрос", Memory())
    assert ans == "делай так и так"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_codex_provider.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.ai.codex'`

- [ ] **Step 3: Реализовать `bukafit/ai/codex.py`**

```python
import asyncio
import json
import re

from bukafit.ai import prompts
from bukafit.ai.mock import MockProvider
from bukafit.ai.provider import Memory
from bukafit.config import settings
from bukafit.core.schemas import ProfileData, ProgramData

_FENCED = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def extract_json(raw: str) -> dict:
    """Достаёт JSON-объект из вывода CLI: сначала из ```-блока, потом первый {...}."""
    m = _FENCED.search(raw)
    candidate = m.group(1) if m else None
    if candidate is None:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = raw[start : end + 1]
    if candidate is None:
        raise ValueError("в выводе нет JSON")
    return json.loads(candidate)


class CodexProvider:
    """Вызывает codex CLI (аутентифицирован через OAuth) как подпроцесс."""

    def __init__(self, bin_path: str | None = None, timeout: int | None = None):
        self.bin = bin_path or settings.codex_bin
        self.timeout = timeout or settings.codex_timeout
        self._fallback = MockProvider()

    async def _run(self, prompt: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            self.bin, "exec", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(prompt.encode()), timeout=self.timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("codex CLI timeout")
        if proc.returncode != 0:
            raise RuntimeError(f"codex CLI error: {err.decode(errors='ignore')[:300]}")
        return out.decode(errors="ignore")

    async def generate_plan(self, profile: ProfileData) -> ProgramData:
        try:
            raw = await self._run(prompts.plan_prompt(profile))
            return ProgramData.model_validate(extract_json(raw))
        except Exception:
            # одна попытка — иначе детерминированный фоллбэк, чтобы юзер не остался без плана
            return await self._fallback.generate_plan(profile)

    async def answer_question(self, question: str, memory: Memory) -> str:
        try:
            return (await self._run(prompts.qa_prompt(question, memory))).strip()
        except Exception:
            return await self._fallback.answer_question(question, memory)
```

> Примечание по CLI: `codex exec -` означает «прочитать промпт из stdin». Точный синтаксис уточняется при установке `codex`; если флаг иной — поправить только `_run` (остальная логика провайдера не меняется). Аутентификация — через ранее выполненный `codex login` (OAuth), ключи в приложении не используются.

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/test_codex_provider.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add bukafit/ai/codex.py tests/test_codex_provider.py
git commit -m "feat: CodexProvider via codex CLI (OAuth) with mock fallback"
```

---

## Task 5: Фабрика провайдера

**Files:**
- Create: `bukafit/ai/factory.py`
- Test: `tests/test_provider_factory.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_provider_factory.py
from bukafit.ai.factory import get_provider
from bukafit.ai.mock import MockProvider
from bukafit.ai.codex import CodexProvider
from bukafit.config import settings


def test_default_is_mock(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "mock")
    assert isinstance(get_provider(), MockProvider)


def test_codex_selected(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "codex")
    assert isinstance(get_provider(), CodexProvider)


def test_unknown_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "whatever")
    assert isinstance(get_provider(), MockProvider)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_provider_factory.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.ai.factory'`

- [ ] **Step 3: Реализовать `bukafit/ai/factory.py`**

```python
from bukafit.ai.codex import CodexProvider
from bukafit.ai.mock import MockProvider
from bukafit.ai.provider import ModelProvider
from bukafit.config import settings


def get_provider() -> ModelProvider:
    if settings.ai_provider == "codex":
        return CodexProvider()
    return MockProvider()
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/test_provider_factory.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add bukafit/ai/factory.py tests/test_provider_factory.py
git commit -m "feat: provider factory (config-driven)"
```

---

## Task 6: Сборка памяти

**Files:**
- Create: `bukafit/ai/memory.py`
- Test: `tests/test_memory.py`

- [ ] **Step 1: Написать падающий тест** (использует фикстуру `session` из Плана 1)

```python
# tests/test_memory.py
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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_memory.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.ai.memory'`

- [ ] **Step 3: Реализовать `bukafit/ai/memory.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.ai.provider import Memory
from bukafit.db import repositories as repo


async def build_memory(session: AsyncSession, user_id: int) -> Memory:
    profile = await repo.get_profile(session, user_id)
    program = await repo.get_active_program(session, user_id)
    summary = await repo.get_summary(session, user_id)

    recent: list[str] = []
    if program:
        for day in program.days:
            for ex in day.exercises:
                last = await repo.last_log(session, user_id, ex.key)
                if last:
                    weight = f"{last.weight}кг" if last.weight is not None else "свой вес"
                    recent.append(f"{ex.name}: {weight} x {last.reps} (RPE {last.rpe})")

    return Memory(
        profile=profile,
        program=program,
        recent=recent,
        summary=summary.text if summary else "",
    )
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/test_memory.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add bukafit/ai/memory.py tests/test_memory.py
git commit -m "feat: compact memory builder (profile + training state + summary)"
```

---

## Task 7: Клавиатуры

**Files:**
- Create: `bukafit/bot/__init__.py` (пустой), `bukafit/bot/keyboards.py`
- Test: `tests/test_keyboards.py`

- [ ] **Step 1: Создать `bukafit/bot/__init__.py`** (пустой)

- [ ] **Step 2: Написать падающий тест**

```python
# tests/test_keyboards.py
from bukafit.bot import keyboards as kb


def test_goal_kb_has_three_options():
    markup = kb.goal_kb()
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert len(buttons) == 3
    assert all(b.callback_data.startswith("goal:") for b in buttons)


def test_days_kb_has_seven_plus_done():
    markup = kb.days_kb(selected=set())
    buttons = [b for row in markup.inline_keyboard for b in row]
    assert len([b for b in buttons if b.callback_data.startswith("day:")]) == 7
    assert any(b.callback_data == "days:done" for b in buttons)


def test_days_kb_marks_selected():
    markup = kb.days_kb(selected={1, 3})
    texts = [b.text for row in markup.inline_keyboard for b in row]
    assert any("✅" in t for t in texts)


def test_log_kb_for_exercise():
    markup = kb.log_kb("squat")
    cbs = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert "log:squat:done" in cbs
    assert "log:squat:skip" in cbs
```

- [ ] **Step 3: Запустить — убедиться, что падает**

Run: `pytest tests/test_keyboards.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.bot.keyboards'`

- [ ] **Step 4: Реализовать `bukafit/bot/keyboards.py`**

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bukafit.core.schemas import Goal, Inventory, Level

WEEKDAYS = {1: "Пн", 2: "Вт", 3: "Ср", 4: "Чт", 5: "Пт", 6: "Сб", 7: "Вс"}


def goal_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💪 Набор массы", callback_data=f"goal:{Goal.MASS.value}")
    b.button(text="🔥 Сушка", callback_data=f"goal:{Goal.CUT.value}")
    b.button(text="🧘 Здоровье", callback_data=f"goal:{Goal.HEALTH.value}")
    b.adjust(1)
    return b.as_markup()


def level_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🌱 Новичок", callback_data=f"level:{Level.BEGINNER.value}")
    b.button(text="⚙️ Средний", callback_data=f"level:{Level.INTERMEDIATE.value}")
    b.button(text="🏆 Опытный", callback_data=f"level:{Level.ADVANCED.value}")
    b.adjust(1)
    return b.as_markup()


def inventory_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏋️ Зал", callback_data=f"inv:{Inventory.GYM.value}")
    b.button(text="🏠 Дом", callback_data=f"inv:{Inventory.HOME.value}")
    b.adjust(2)
    return b.as_markup()


def days_kb(selected: set[int]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for num, name in WEEKDAYS.items():
        mark = "✅ " if num in selected else ""
        b.button(text=f"{mark}{name}", callback_data=f"day:{num}")
    b.button(text="Готово ▶️", callback_data="days:done")
    b.adjust(4, 3, 1)
    return b.as_markup()


def skip_injuries_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Нет ограничений ▶️", callback_data="injuries:none")
    return b.as_markup()


def log_kb(exercise_key: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Сделал", callback_data=f"log:{exercise_key}:done")
    b.button(text="➖ вес", callback_data=f"log:{exercise_key}:wdown")
    b.button(text="➕ вес", callback_data=f"log:{exercise_key}:wup")
    b.button(text="⏭️ Пропустить", callback_data=f"log:{exercise_key}:skip")
    b.adjust(1, 2, 1)
    return b.as_markup()
```

- [ ] **Step 5: Запустить тесты — должны пройти**

Run: `pytest tests/test_keyboards.py -q`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add bukafit/bot/__init__.py bukafit/bot/keyboards.py tests/test_keyboards.py
git commit -m "feat: inline keyboards (onboarding + logging)"
```

---

## Task 8: DB-middleware

**Files:**
- Create: `bukafit/bot/middleware.py`

- [ ] **Step 1: Реализовать `bukafit/bot/middleware.py`**

```python
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from bukafit.db import repositories as repo
from bukafit.db.session import SessionMaker


class DBMiddleware(BaseMiddleware):
    """Открывает сессию на апдейт, кладёт session + user в data, коммитит в конце."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        async with SessionMaker() as session:
            data["session"] = session
            if tg_user is not None:
                data["user"] = await repo.get_or_create_user(session, tg_user.id)
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
```

- [ ] **Step 2: Проверить импорт**

Run: `. .venv/bin/activate && python -c "from bukafit.bot.middleware import DBMiddleware; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add bukafit/bot/middleware.py
git commit -m "feat: DB middleware (session + user injection)"
```

---

## Task 9: Хендлеры — common (/start /help /progress)

**Files:**
- Create: `bukafit/bot/handlers/__init__.py` (пустой), `bukafit/bot/handlers/common.py`

- [ ] **Step 1: Создать `bukafit/bot/handlers/__init__.py`** (пустой)

- [ ] **Step 2: Реализовать `bukafit/bot/handlers/common.py`**

```python
from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.bot.handlers.onboarding import start_onboarding
from bukafit.core.models import User, WorkoutLog
from bukafit.core.streaks import current_streak
from bukafit.db import repositories as repo

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, session: AsyncSession, user: User, state: FSMContext):
    profile = await repo.get_profile(session, user.id)
    if profile is None:
        await message.answer(
            "Привет! Я тренер BukaFit 💪 Помогу собрать программу и вести тренировки.\n"
            "Давай за минуту настроимся."
        )
        await start_onboarding(message, state)
        return
    await message.answer(
        "С возвращением! 👋\n"
        "/today — тренировка на сегодня\n"
        "/progress — твой прогресс\n"
        "Или просто напиши вопрос про тренировки и питание."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "Что я умею:\n"
        "/today — план на сегодня и отметка тренировки\n"
        "/progress — серия и активность за неделю\n"
        "/start — пройти настройку заново\n\n"
        "Ещё можешь спросить меня про технику, замену упражнения или питание."
    )


@router.message(Command("progress"))
async def cmd_progress(message: Message, session: AsyncSession, user: User):
    week = await repo.weekly_done_count(session, user.id)
    rows = await session.scalars(
        select(WorkoutLog.created_at).where(
            WorkoutLog.user_id == user.id, WorkoutLog.done.is_(True)
        )
    )
    dates = [d.astimezone(timezone.utc).date() for d in rows.all()]
    streak = current_streak(dates, today=datetime.now(timezone.utc).date())
    await message.answer(
        f"📊 Твой прогресс:\n"
        f"• Тренировок за неделю: {week}\n"
        f"• Серия подряд: {streak} дн.\n\n"
        + ("Так держать! 🔥" if week >= 2 else "Давай хотя бы 2 тренировки на неделе 💪")
    )
```

- [ ] **Step 3: Проверить импорт** (после Task 10 onboarding появится; пока проверим синтаксис парсингом)

Run: `. .venv/bin/activate && python -c "import ast; ast.parse(open('bukafit/bot/handlers/common.py').read()); print('syntax ok')"`
Expected: `syntax ok`

> Полный импорт-чек делаем в Task 13 (smoke), когда все хендлеры готовы.

- [ ] **Step 4: Commit**

```bash
git add bukafit/bot/handlers/__init__.py bukafit/bot/handlers/common.py
git commit -m "feat: common handlers (/start /help /progress)"
```

---

## Task 10: Хендлеры — онбординг (FSM)

**Files:**
- Create: `bukafit/bot/handlers/onboarding.py`

- [ ] **Step 1: Реализовать `bukafit/bot/handlers/onboarding.py`**

```python
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.ai.provider import ModelProvider
from bukafit.bot import keyboards as kb
from bukafit.core.models import User
from bukafit.core.schemas import Goal, Inventory, Level, ProfileData
from bukafit.db import repositories as repo

router = Router()


class Onboarding(StatesGroup):
    goal = State()
    level = State()
    inventory = State()
    days = State()
    injuries = State()


async def start_onboarding(message: Message, state: FSMContext):
    await state.set_state(Onboarding.goal)
    await message.answer("Какая цель?", reply_markup=kb.goal_kb())


@router.callback_query(Onboarding.goal, F.data.startswith("goal:"))
async def pick_goal(cb: CallbackQuery, state: FSMContext):
    await state.update_data(goal=cb.data.split(":")[1])
    await state.set_state(Onboarding.level)
    await cb.message.edit_text("Твой уровень?", reply_markup=kb.level_kb())
    await cb.answer()


@router.callback_query(Onboarding.level, F.data.startswith("level:"))
async def pick_level(cb: CallbackQuery, state: FSMContext):
    await state.update_data(level=cb.data.split(":")[1])
    await state.set_state(Onboarding.inventory)
    await cb.message.edit_text("Где тренируешься?", reply_markup=kb.inventory_kb())
    await cb.answer()


@router.callback_query(Onboarding.inventory, F.data.startswith("inv:"))
async def pick_inventory(cb: CallbackQuery, state: FSMContext):
    await state.update_data(inventory=cb.data.split(":")[1], days=[])
    await state.set_state(Onboarding.days)
    await cb.message.edit_text(
        "В какие дни недели удобно? Отметь и нажми «Готово».",
        reply_markup=kb.days_kb(set()),
    )
    await cb.answer()


@router.callback_query(Onboarding.days, F.data.startswith("day:"))
async def toggle_day(cb: CallbackQuery, state: FSMContext):
    num = int(cb.data.split(":")[1])
    data = await state.get_data()
    days = set(data.get("days", []))
    days.symmetric_difference_update({num})
    await state.update_data(days=sorted(days))
    await cb.message.edit_reply_markup(reply_markup=kb.days_kb(days))
    await cb.answer()


@router.callback_query(Onboarding.days, F.data == "days:done")
async def days_done(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("days"):
        await cb.answer("Выбери хотя бы один день", show_alert=True)
        return
    await state.set_state(Onboarding.injuries)
    await cb.message.edit_text(
        "Есть травмы или ограничения? Напиши коротко (или нажми кнопку).",
        reply_markup=kb.skip_injuries_kb(),
    )
    await cb.answer()


@router.callback_query(Onboarding.injuries, F.data == "injuries:none")
async def injuries_none(
    cb: CallbackQuery, state: FSMContext, session: AsyncSession, user: User,
    provider: ModelProvider,
):
    await _finish(cb.message, state, session, user, provider, injuries=[])
    await cb.answer()


@router.message(Onboarding.injuries, F.text)
async def injuries_text(
    message: Message, state: FSMContext, session: AsyncSession, user: User,
    provider: ModelProvider,
):
    injuries = [s.strip() for s in message.text.split(",") if s.strip()]
    await _finish(message, state, session, user, provider, injuries=injuries)


async def _finish(message, state, session, user, provider, injuries):
    data = await state.get_data()
    profile = ProfileData(
        goal=Goal(data["goal"]),
        level=Level(data["level"]),
        inventory=Inventory(data["inventory"]),
        days=data["days"],
        injuries=injuries,
    )
    await repo.save_profile(session, user.id, profile)
    await state.clear()

    await message.answer("Собираю программу под тебя… ⏳")
    program = await provider.generate_plan(profile)
    await repo.save_program(session, user.id, program)

    lines = [f"Готово! Твоя программа ({len(program.days)} дн./нед.):", ""]
    for day in sorted(program.days, key=lambda d: d.weekday):
        lines.append(f"• {day.title}: " + ", ".join(ex.name for ex in day.exercises))
    lines += ["", "Команда /today покажет тренировку на сегодня. Погнали! 💪"]
    await message.answer("\n".join(lines))
```

- [ ] **Step 2: Проверить синтаксис**

Run: `. .venv/bin/activate && python -c "import ast; ast.parse(open('bukafit/bot/handlers/onboarding.py').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 3: Commit**

```bash
git add bukafit/bot/handlers/onboarding.py
git commit -m "feat: onboarding FSM (goal/level/inventory/days/injuries -> plan)"
```

---

## Task 11: Хендлеры — тренировка (today + логирование)

**Files:**
- Create: `bukafit/bot/handlers/training.py`

- [ ] **Step 1: Реализовать `bukafit/bot/handlers/training.py`**

```python
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.bot import keyboards as kb
from bukafit.core.models import User
from bukafit.core.progression import suggest
from bukafit.core.schedule import next_workout, workout_for_today
from bukafit.core.schemas import LogData
from bukafit.db import repositories as repo

router = Router()


def _today_weekday() -> int:
    return datetime.now(timezone.utc).isoweekday()  # Пн=1..Вс=7


async def _exercise_card(session: AsyncSession, user_id: int, ex) -> str:
    last = await repo.last_log(session, user_id, ex.key)
    s = suggest(last, ex)
    weight = f"{s.weight} кг" if s.weight is not None else "свой вес"
    return (
        f"<b>{ex.name}</b>\n"
        f"Цель: {ex.sets}×{s.reps}, {weight} ({s.note})\n"
        f"Отдых: {ex.rest_sec} сек"
    )


@router.message(Command("today"))
async def cmd_today(message: Message, session: AsyncSession, user: User):
    program = await repo.get_active_program(session, user.id)
    if program is None:
        await message.answer("Программы пока нет. Набери /start, соберём её.")
        return

    day = workout_for_today(program, _today_weekday())
    if day is None:
        nxt = next_workout(program, _today_weekday())
        if nxt:
            await message.answer(
                f"Сегодня день отдыха 😌 Ближайшая тренировка: <b>{nxt.title}</b>."
            )
        else:
            await message.answer("Сегодня отдых 😌")
        return

    await message.answer(f"🏋️ Сегодня: <b>{day.title}</b>")
    for ex in day.exercises:
        await message.answer(
            await _exercise_card(session, user.id, ex),
            reply_markup=kb.log_kb(ex.key),
        )


def _find_exercise(program, key):
    for day in program.days:
        for ex in day.exercises:
            if ex.key == key:
                return ex
    return None


@router.callback_query(F.data.startswith("log:"))
async def on_log(cb: CallbackQuery, session: AsyncSession, user: User):
    _, key, action = cb.data.split(":")
    program = await repo.get_active_program(session, user.id)
    ex = _find_exercise(program, key) if program else None
    if ex is None:
        await cb.answer("Упражнение не найдено", show_alert=True)
        return

    last = await repo.last_log(session, user.id, key)
    s = suggest(last, ex)
    weight = s.weight

    if action == "skip":
        await repo.add_log(session, user.id, key, done=False, data=LogData(weight=weight, reps=0))
        await cb.message.edit_text(f"⏭️ {ex.name} — пропущено")
        await cb.answer()
        return

    if action == "wup" and weight is not None:
        weight += 2.5
    elif action == "wdown" and weight is not None:
        weight = max(0.0, weight - 2.5)

    if action in ("wup", "wdown"):
        # обновили предложенный вес — перерисуем карточку, лог пишем при «Сделал»
        await cb.message.edit_text(
            f"<b>{ex.name}</b>\nЦель: {ex.sets}×{s.reps}, "
            f"{(str(weight) + ' кг') if weight is not None else 'свой вес'}",
            reply_markup=kb.log_kb(key),
        )
        await cb.answer("Вес обновлён")
        return

    # action == "done"
    await repo.add_log(
        session, user.id, key, done=True,
        data=LogData(weight=weight, reps=s.reps, rpe=7),
    )
    await cb.message.edit_text(
        f"✅ {ex.name} — записал: "
        f"{(str(weight) + ' кг') if weight is not None else 'свой вес'} × {s.reps}"
    )
    await cb.answer("Записал 💪")
```

- [ ] **Step 2: Проверить синтаксис**

Run: `. .venv/bin/activate && python -c "import ast; ast.parse(open('bukafit/bot/handlers/training.py').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 3: Commit**

```bash
git add bukafit/bot/handlers/training.py
git commit -m "feat: training handlers (/today + inline logging)"
```

---

## Task 12: Хендлеры — чат (свободный текст → ИИ)

**Files:**
- Create: `bukafit/bot/handlers/chat.py`

- [ ] **Step 1: Реализовать `bukafit/bot/handlers/chat.py`**

```python
from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.ai.memory import build_memory
from bukafit.ai.provider import ModelProvider
from bukafit.core.models import User

router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def on_text(
    message: Message, session: AsyncSession, user: User, provider: ModelProvider
):
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    memory = await build_memory(session, user.id)
    answer = await provider.answer_question(message.text, memory)
    await message.answer(answer)
```

> Этот роутер подключается ПОСЛЕДНИМ (catch-all по тексту), чтобы не перехватывать ввод во время онбординга (там стоят FSM-фильтры состояний выше по приоритету).

- [ ] **Step 2: Проверить синтаксис**

Run: `. .venv/bin/activate && python -c "import ast; ast.parse(open('bukafit/bot/handlers/chat.py').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 3: Commit**

```bash
git add bukafit/bot/handlers/chat.py
git commit -m "feat: chat handler (free text -> AI answer)"
```

---

## Task 13: Точка входа бота + сборка

**Files:**
- Create: `bukafit/bot/main.py`

- [ ] **Step 1: Реализовать `bukafit/bot/main.py`**

```python
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bukafit.ai.factory import get_provider
from bukafit.bot.handlers import chat, common, onboarding, training
from bukafit.bot.middleware import DBMiddleware
from bukafit.config import settings


def build_dispatcher() -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    dp.update.outer_middleware(DBMiddleware())
    dp["provider"] = get_provider()

    # порядок важен: chat — последний (catch-all по тексту)
    dp.include_router(common.router)
    dp.include_router(onboarding.router)
    dp.include_router(training.router)
    dp.include_router(chat.router)
    return dp


async def run_polling() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


def main() -> None:
    asyncio.run(run_polling())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Полный импорт-чек всех хендлеров и сборки**

Run: `. .venv/bin/activate && python -c "from bukafit.bot.main import build_dispatcher; print('import ok')"`
Expected: `import ok` (без ошибок импорта по всем модулям bot/ai).

> Если падает на отсутствии Redis — это норм для импорта (storage создаётся внутри функции, но from_url не коннектится сразу). Если ошибка про aiogram API — поправить под установленную версию aiogram 3.x.

- [ ] **Step 3: Smoke-тест с реальным ботом (ручной)**

1. Создать бота у @BotFather, получить токен, положить в `.env` (`BOT_TOKEN=...`).
2. Поднять инфраструктуру: `docker compose up -d db redis` и `alembic upgrade head`.
3. Запустить: `. .venv/bin/activate && python -m bukafit.bot.main`
4. В Telegram: `/start` → пройти онбординг → получить программу → `/today` → отметить упражнение → `/progress` → задать вопрос текстом.

Expected: онбординг доходит до программы; `/today` показывает карточки с кнопками; «Сделал» пишет лог; вопрос текстом возвращает ответ с дисклеймером.

- [ ] **Step 4: Commit**

```bash
git add bukafit/bot/main.py
git commit -m "feat: bot entrypoint (dispatcher, routers, polling)"
```

---

## Task 14: Напоминания (APScheduler)

**Files:**
- Create: `bukafit/reminders/__init__.py` (пустой), `bukafit/reminders/scheduler.py`
- Modify: `bukafit/bot/main.py` (запустить планировщик)

- [ ] **Step 1: Создать `bukafit/reminders/__init__.py`** (пустой)

- [ ] **Step 2: Реализовать `bukafit/reminders/scheduler.py`**

```python
import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from bukafit.config import settings
from bukafit.core.models import User
from bukafit.core.schedule import workout_for_today
from bukafit.db import repositories as repo
from bukafit.db.session import SessionMaker

log = logging.getLogger(__name__)


def _today_weekday() -> int:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoweekday()


async def morning_plan(bot: Bot) -> None:
    async with SessionMaker() as session:
        users = (await session.scalars(select(User))).all()
        wd = _today_weekday()
        for user in users:
            program = await repo.get_active_program(session, user.id)
            if not program:
                continue
            day = workout_for_today(program, wd)
            text = (
                f"☀️ Доброе утро! Сегодня: <b>{day.title}</b>. Набери /today."
                if day else "☀️ Доброе утро! Сегодня день отдыха — восстанавливайся 😌"
            )
            try:
                await bot.send_message(user.tg_id, text)
            except Exception as e:  # noqa: BLE001
                log.warning("morning send failed for %s: %s", user.tg_id, e)


async def evening_check(bot: Bot) -> None:
    async with SessionMaker() as session:
        users = (await session.scalars(select(User))).all()
        for user in users:
            done = await repo.weekly_done_count(session, user.id)
            try:
                await bot.send_message(
                    user.tg_id,
                    f"🌙 Итог дня. Тренировок за неделю: {done}. "
                    + ("Красава! 🔥" if done >= 2 else "Завтра наверстаем 💪"),
                )
            except Exception as e:  # noqa: BLE001
                log.warning("evening send failed for %s: %s", user.tg_id, e)


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(morning_plan, "cron", hour=8, minute=0, args=[bot])
    scheduler.add_job(evening_check, "cron", hour=21, minute=0, args=[bot])
    scheduler.start()
    return scheduler
```

- [ ] **Step 3: Подключить планировщик в `bukafit/bot/main.py`**

Изменить функцию `run_polling` — добавить запуск планировщика после создания бота:

```python
async def run_polling() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher()

    from bukafit.reminders.scheduler import start_scheduler
    start_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
```

- [ ] **Step 4: Проверить импорт**

Run: `. .venv/bin/activate && python -c "from bukafit.reminders.scheduler import start_scheduler; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add bukafit/reminders bukafit/bot/main.py
git commit -m "feat: reminders (morning plan + evening check via APScheduler)"
```

---

## Task 15: Финальный прогон

- [ ] **Step 1: Все тесты**

Run: `. .venv/bin/activate && pytest -q`
Expected: PASS — все тесты Плана 1 и Плана 2 зелёные.

- [ ] **Step 2: Линт**

Run: `. .venv/bin/activate && ruff check bukafit tests`
Expected: `All checks passed!` (иначе исправить и повторить).

- [ ] **Step 3: Commit (если правки)**

```bash
git add -A
git commit -m "chore: lint pass for bot + ai" || echo "nothing to commit"
```

---

## Definition of Done (План 2)

- [ ] `pytest -q` — всё зелёное (mock/codex/factory/memory/keyboards + ядро из Плана 1).
- [ ] `python -m bukafit.bot.main` запускает бота (polling).
- [ ] Онбординг → генерация плана (mock) → `/today` → логирование → `/progress` работают вручную.
- [ ] Чат-вопрос возвращает ответ с дисклеймером.
- [ ] `AI_PROVIDER=codex` переключает на CodexProvider (требует `codex login`); фоллбэк на mock при сбое.
- [ ] Напоминания утром/вечером поставлены в планировщик.

---

## Что осознанно отложено (v2, BukaFit.md §12)

- Webhook-режим для прода (сейчас polling; webhook добавим при деплое).
- Реальные API-провайдеры Gemini/Claude (через тот же `factory`).
- Rolling summary: авто-пересборка (`save_summary` уже есть, авто-уплотнение — позже).
- Питание/фото еды, носимые устройства, биллинг.
