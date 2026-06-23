# BukaFit — План 1: Каркас, хранение, доменная логика

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать проект, инфраструктуру (Docker PG+Redis), слой хранения (JSONB + Pydantic) и чистую доменную логику (прогрессия, расписание, стрики) с тестами.

**Architecture:** Модульный монолит на Python. Доменные объекты — Pydantic-схемы, сериализуются в Postgres JSONB через гибридные SQLAlchemy-модели (индекс-колонки + `data` JSONB). Чистая логика (`progression`/`schedule`/`streaks`) не зависит от БД и ИИ — тестируется как чистые функции.

**Tech Stack:** Python 3.12, SQLAlchemy 2 (async, asyncpg), Pydantic v2, Alembic, Postgres, Redis, Docker Compose, pytest + pytest-asyncio.

**Предусловие окружения:** установлены Python 3.12 и Docker. Репозиторий уже инициализирован (`git`), есть `.gitignore` и `docs/`.

---

## Структура файлов (создаётся этим планом)

```
pyproject.toml              # пакет + зависимости + pytest/ruff конфиг
.env.example                # пример переменных окружения
docker-compose.yml          # postgres + redis (+ app позже)
Dockerfile                  # образ приложения
alembic.ini                 # конфиг миграций
migrations/                 # alembic env + версии
bukafit/
  __init__.py
  config.py                 # pydantic-settings Settings
  core/
    __init__.py
    schemas.py              # Pydantic: ProfileData, ProgramData, LogData, ...
    models.py               # SQLAlchemy: Base, User, Profile, Program, WorkoutLog, Summary
    progression.py          # suggest(last, plan) -> Suggestion
    schedule.py             # workout_for_today / next_workout
    streaks.py              # current_streak(dates)
  db/
    __init__.py
    session.py              # async engine + sessionmaker
    repositories.py         # доступ к данным (функции над AsyncSession)
tests/
  __init__.py
  conftest.py               # фикстуры БД
  test_schemas.py
  test_progression.py
  test_schedule.py
  test_streaks.py
  test_repositories.py
```

> Примечание: спека указывала `core/models/` как пакет; для текущего размера используем один модуль `core/models.py` (одна ответственность, проще держать в контексте). При росте — разобьём.

---

## Task 1: Скаффолд проекта

**Files:**
- Create: `pyproject.toml`
- Create: `bukafit/__init__.py`, `bukafit/core/__init__.py`, `bukafit/db/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Создать `pyproject.toml`**

```toml
[project]
name = "bukafit"
version = "0.1.0"
description = "BukaFit AI-тренер — Telegram-бот"
requires-python = ">=3.12"
dependencies = [
    "aiogram>=3.13",
    "SQLAlchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",
    "redis>=5.0",
    "APScheduler>=3.10",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["bukafit*"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

- [ ] **Step 2: Создать пустые `__init__.py`**

Создать 4 пустых файла: `bukafit/__init__.py`, `bukafit/core/__init__.py`, `bukafit/db/__init__.py`, `tests/__init__.py`.

- [ ] **Step 3: Создать venv и установить зависимости**

Run:
```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```
Expected: установка без ошибок, в конце `Successfully installed ... bukafit-0.1.0 ...`.

- [ ] **Step 4: Проверить, что pytest запускается**

Run: `. .venv/bin/activate && pytest -q`
Expected: `no tests ran` (нет тестов — это норм, главное pytest стартует без ImportError).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml bukafit tests
git commit -m "chore: project scaffold (pyproject, packages, deps)"
```

---

## Task 2: Конфиг (pydantic-settings)

**Files:**
- Create: `bukafit/config.py`
- Create: `.env.example`

- [ ] **Step 1: Создать `bukafit/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    bot_token: str = "test-token"

    # Хранилища
    database_url: str = "postgresql+asyncpg://bukafit:bukafit@localhost:5432/bukafit"
    redis_url: str = "redis://localhost:6379/0"

    # ИИ-провайдер
    ai_provider: str = "mock"  # mock | codex
    codex_bin: str = "codex"
    codex_timeout: int = 60

    # Режим Telegram
    use_webhook: bool = False
    webhook_url: str = ""
    webhook_path: str = "/webhook"
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    # Прочее
    tz: str = "Asia/Tashkent"


settings = Settings()
```

- [ ] **Step 2: Создать `.env.example`**

```bash
BOT_TOKEN=put-telegram-bot-token-here
DATABASE_URL=postgresql+asyncpg://bukafit:bukafit@localhost:5432/bukafit
REDIS_URL=redis://localhost:6379/0
AI_PROVIDER=mock
CODEX_BIN=codex
CODEX_TIMEOUT=60
USE_WEBHOOK=false
TZ=Asia/Tashkent
```

- [ ] **Step 3: Проверить импорт конфига**

Run: `. .venv/bin/activate && python -c "from bukafit.config import settings; print(settings.ai_provider, settings.tz)"`
Expected: `mock Asia/Tashkent`

- [ ] **Step 4: Commit**

```bash
git add bukafit/config.py .env.example
git commit -m "feat: settings via pydantic-settings + .env.example"
```

---

## Task 3: Доменные Pydantic-схемы

**Files:**
- Create: `bukafit/core/schemas.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_schemas.py
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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_schemas.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.core.schemas'`

- [ ] **Step 3: Реализовать `bukafit/core/schemas.py`**

```python
from enum import Enum

from pydantic import BaseModel, Field


class Goal(str, Enum):
    MASS = "mass"      # набор массы
    CUT = "cut"        # сушка
    HEALTH = "health"  # здоровье/тонус


class Level(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class Inventory(str, Enum):
    GYM = "gym"
    HOME = "home"


class ProfileData(BaseModel):
    goal: Goal
    level: Level
    inventory: Inventory
    days: list[int] = Field(default_factory=list)  # дни недели 1..7 (Пн=1)
    injuries: list[str] = Field(default_factory=list)
    notes: str = ""


class ExercisePlan(BaseModel):
    key: str                       # слаг упражнения, напр. "squat"
    name: str                      # человекочитаемое имя
    sets: int = 3
    target_reps: int = 10
    target_weight: float | None = None  # None = без веса (свой вес)
    rest_sec: int = 90
    alternatives: list[str] = Field(default_factory=list)


class DayPlan(BaseModel):
    weekday: int                   # 1..7 (Пн=1)
    title: str
    exercises: list[ExercisePlan] = Field(default_factory=list)


class ProgramData(BaseModel):
    days: list[DayPlan] = Field(default_factory=list)
    note: str = ""


class LogData(BaseModel):
    weight: float | None = None
    reps: int = 0
    rpe: int = 7                   # 1..10 субъективная нагрузка
    note: str = ""


class SummaryData(BaseModel):
    text: str = ""
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/test_schemas.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add bukafit/core/schemas.py tests/test_schemas.py
git commit -m "feat: domain Pydantic schemas (profile, program, log, summary)"
```

---

## Task 4: SQLAlchemy-модели (гибрид JSONB)

**Files:**
- Create: `bukafit/core/models.py`

- [ ] **Step 1: Реализовать `bukafit/core/models.py`**

(Модели проверяются интеграционно в Task 8; здесь — только определение + проверка импорта и metadata.)

```python
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    access_status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    data: Mapped[dict] = mapped_column(JSONB)


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    data: Mapped[dict] = mapped_column(JSONB)


class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    exercise_key: Mapped[str] = mapped_column(String(64), index=True)
    done: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    data: Mapped[dict] = mapped_column(JSONB)


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    data: Mapped[dict] = mapped_column(JSONB)
```

- [ ] **Step 2: Проверить импорт и таблицы**

Run:
```bash
. .venv/bin/activate && python -c "from bukafit.core.models import Base; print(sorted(Base.metadata.tables))"
```
Expected: `['profiles', 'programs', 'summaries', 'users', 'workout_logs']`

- [ ] **Step 3: Commit**

```bash
git add bukafit/core/models.py
git commit -m "feat: SQLAlchemy models (JSONB hybrid storage)"
```

---

## Task 5: Docker Compose (Postgres + Redis) + Dockerfile

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile`

- [ ] **Step 1: Создать `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: bukafit
      POSTGRES_PASSWORD: bukafit
      POSTGRES_DB: bukafit
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U bukafit"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
```

- [ ] **Step 2: Создать `Dockerfile`** (для приложения, используется в Плане 2)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install -U pip && pip install -e .

COPY . .

CMD ["python", "-m", "bukafit.bot.main"]
```

- [ ] **Step 3: Поднять БД и Redis, проверить готовность**

Run:
```bash
docker compose up -d db redis
docker compose ps
```
Expected: оба сервиса `running`/`healthy`.

- [ ] **Step 4: Проверить подключение к Postgres**

Run: `docker compose exec db pg_isready -U bukafit`
Expected: `accepting connections`

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml Dockerfile
git commit -m "chore: docker compose (postgres + redis) and app Dockerfile"
```

---

## Task 6: Alembic + первая миграция

**Files:**
- Create: `alembic.ini`
- Create: `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/` (auto)

- [ ] **Step 1: Инициализировать Alembic (async-шаблон)**

Run: `. .venv/bin/activate && alembic init -t async migrations`
Expected: создан `alembic.ini` и каталог `migrations/`.

- [ ] **Step 2: Прописать URL и target_metadata в `migrations/env.py`**

Заменить две вещи. (а) В начало `migrations/env.py`, после существующих импортов, добавить:

```python
from bukafit.config import settings
from bukafit.core.models import Base
import bukafit.core.models  # noqa: F401  (регистрирует таблицы)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata
```

(б) Найти строку `target_metadata = None` и удалить её (заменена выше).

- [ ] **Step 3: Сгенерировать миграцию**

Run (БД должна быть поднята из Task 5):
```bash
. .venv/bin/activate && alembic revision --autogenerate -m "init schema"
```
Expected: создан файл в `migrations/versions/`, в нём `op.create_table("users" ...)` и остальные 4 таблицы.

- [ ] **Step 4: Применить миграцию и проверить таблицы**

Run:
```bash
. .venv/bin/activate && alembic upgrade head
docker compose exec db psql -U bukafit -d bukafit -c "\dt"
```
Expected: в списке таблиц — `users, profiles, programs, workout_logs, summaries, alembic_version`.

- [ ] **Step 5: Commit**

```bash
git add alembic.ini migrations
git commit -m "feat: alembic async migrations + init schema"
```

---

## Task 7: Async-сессия БД

**Files:**
- Create: `bukafit/db/session.py`

- [ ] **Step 1: Реализовать `bukafit/db/session.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bukafit.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionMaker = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionMaker() as session:
        yield session
```

- [ ] **Step 2: Проверить подключение к живой БД**

Run (БД поднята):
```bash
. .venv/bin/activate && python -c "
import asyncio
from sqlalchemy import text
from bukafit.db.session import SessionMaker

async def main():
    async with SessionMaker() as s:
        r = await s.execute(text('select 1'))
        print('db ok', r.scalar_one())

asyncio.run(main())
"
```
Expected: `db ok 1`

- [ ] **Step 3: Commit**

```bash
git add bukafit/db/session.py
git commit -m "feat: async db engine + session factory"
```

---

## Task 8: Репозитории (доступ к данным)

**Files:**
- Create: `bukafit/db/repositories.py`
- Create: `tests/conftest.py`
- Test: `tests/test_repositories.py`

> Тесты репозиториев работают против живой БД из Docker (Task 5) и применённых миграций (Task 6). Каждый тест — в транзакции с откатом (изоляция).

- [ ] **Step 1: Создать `tests/conftest.py`**

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.db.session import engine, SessionMaker


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """Сессия в транзакции с откатом после теста — чистая изоляция."""
    conn = await engine.connect()
    trans = await conn.begin()
    sess = AsyncSession(bind=conn, expire_on_commit=False)
    try:
        yield sess
    finally:
        await sess.close()
        await trans.rollback()
        await conn.close()
```

- [ ] **Step 2: Написать падающий тест**

```python
# tests/test_repositories.py
import pytest

from bukafit.core.schemas import (
    Goal, Level, Inventory, ProfileData,
    ProgramData, DayPlan, ExercisePlan, LogData,
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
    # считаем только выполненные
    assert await repo.weekly_done_count(session, user.id) == 1
```

- [ ] **Step 3: Запустить — убедиться, что падает**

Run: `pytest tests/test_repositories.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.db.repositories'`

- [ ] **Step 4: Реализовать `bukafit/db/repositories.py`**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bukafit.core.models import Profile, Program, Summary, User, WorkoutLog
from bukafit.core.schemas import LogData, ProfileData, ProgramData, SummaryData


async def get_or_create_user(session: AsyncSession, tg_id: int) -> User:
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if user is None:
        user = User(tg_id=tg_id)
        session.add(user)
        await session.flush()
    return user


async def get_profile(session: AsyncSession, user_id: int) -> ProfileData | None:
    row = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    return ProfileData.model_validate(row.data) if row else None


async def save_profile(session: AsyncSession, user_id: int, data: ProfileData) -> None:
    row = await session.scalar(select(Profile).where(Profile.user_id == user_id))
    if row is None:
        session.add(Profile(user_id=user_id, data=data.model_dump(mode="json")))
    else:
        row.data = data.model_dump(mode="json")
    await session.flush()


async def get_active_program(session: AsyncSession, user_id: int) -> ProgramData | None:
    row = await session.scalar(
        select(Program).where(Program.user_id == user_id, Program.is_active.is_(True))
    )
    return ProgramData.model_validate(row.data) if row else None


async def save_program(session: AsyncSession, user_id: int, data: ProgramData) -> None:
    await session.execute(
        update(Program).where(Program.user_id == user_id).values(is_active=False)
    )
    session.add(Program(user_id=user_id, is_active=True, data=data.model_dump(mode="json")))
    await session.flush()


async def add_log(
    session: AsyncSession, user_id: int, exercise_key: str, done: bool, data: LogData
) -> None:
    session.add(
        WorkoutLog(
            user_id=user_id,
            exercise_key=exercise_key,
            done=done,
            data=data.model_dump(mode="json"),
        )
    )
    await session.flush()


async def last_log(
    session: AsyncSession, user_id: int, exercise_key: str
) -> LogData | None:
    row = await session.scalar(
        select(WorkoutLog)
        .where(WorkoutLog.user_id == user_id, WorkoutLog.exercise_key == exercise_key)
        .order_by(WorkoutLog.created_at.desc(), WorkoutLog.id.desc())
        .limit(1)
    )
    return LogData.model_validate(row.data) if row else None


async def weekly_done_count(session: AsyncSession, user_id: int) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    rows = await session.scalars(
        select(WorkoutLog).where(
            WorkoutLog.user_id == user_id,
            WorkoutLog.done.is_(True),
            WorkoutLog.created_at >= since,
        )
    )
    return len(rows.all())


async def get_summary(session: AsyncSession, user_id: int) -> SummaryData | None:
    row = await session.scalar(select(Summary).where(Summary.user_id == user_id))
    return SummaryData.model_validate(row.data) if row else None


async def save_summary(session: AsyncSession, user_id: int, data: SummaryData) -> None:
    row = await session.scalar(select(Summary).where(Summary.user_id == user_id))
    if row is None:
        session.add(Summary(user_id=user_id, data=data.model_dump(mode="json")))
    else:
        row.data = data.model_dump(mode="json")
    await session.flush()
```

- [ ] **Step 5: Запустить тесты — должны пройти**

Run: `pytest tests/test_repositories.py -q`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add bukafit/db/repositories.py tests/conftest.py tests/test_repositories.py
git commit -m "feat: repositories (users, profile, program, logs, summary) + db test fixture"
```

---

## Task 9: Прогрессия нагрузки (чистая функция)

**Files:**
- Create: `bukafit/core/progression.py`
- Test: `tests/test_progression.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_progression.py
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
    assert s.weight == 42.5  # +2.5 кг
    assert s.reps == 8


def test_high_rpe_deloads():
    last = LogData(weight=40.0, reps=8, rpe=9)
    s = suggest(last, plan())
    assert s.weight == 36.0  # -10%, округление до 0.5
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
    assert s.reps == 11  # +1 повтор
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_progression.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.core.progression'`

- [ ] **Step 3: Реализовать `bukafit/core/progression.py`**

```python
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

    # Тяжело — делоуд (или держим, если без веса)
    if last.rpe >= HARD_RPE:
        if plan.target_weight is not None and last.weight is not None:
            return Suggestion(
                weight=_round_half(last.weight * DELOAD_FACTOR),
                reps=plan.target_reps,
                note="было тяжело — снизим вес",
            )
        return Suggestion(weight=None, reps=plan.target_reps, note="было тяжело — держим")

    # Достиг цели и не тяжело — прогрессируем
    if hit_target and last.rpe <= EASY_RPE:
        if plan.target_weight is not None and last.weight is not None:
            return Suggestion(
                weight=_round_half(last.weight + WEIGHT_STEP),
                reps=plan.target_reps,
                note="идём вверх по весу",
            )
        return Suggestion(weight=None, reps=last.reps + 1, note="добавим повтор")

    # Иначе — держим целевые значения
    base_weight = last.weight if last.weight is not None else plan.target_weight
    return Suggestion(weight=base_weight, reps=plan.target_reps, note="закрепляем")
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/test_progression.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add bukafit/core/progression.py tests/test_progression.py
git commit -m "feat: deterministic load progression"
```

---

## Task 10: Расписание тренировок (чистая функция)

**Files:**
- Create: `bukafit/core/schedule.py`
- Test: `tests/test_schedule.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_schedule.py
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
    assert d.title == "Верх"  # ближайший вперёд — среда


def test_next_wraps_around_week():
    d = next_workout(prog(), weekday=6)
    assert d.title == "Низ"  # оборачивается на понедельник


def test_next_empty_program():
    assert next_workout(ProgramData(), weekday=1) is None
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_schedule.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.core.schedule'`

- [ ] **Step 3: Реализовать `bukafit/core/schedule.py`**

```python
from bukafit.core.schemas import DayPlan, ProgramData


def workout_for_today(program: ProgramData, weekday: int) -> DayPlan | None:
    for day in program.days:
        if day.weekday == weekday:
            return day
    return None


def next_workout(program: ProgramData, weekday: int) -> DayPlan | None:
    if not program.days:
        return None
    # ближайший день вперёд по неделе (1..7), с оборотом
    ordered = sorted(program.days, key=lambda d: d.weekday)
    for day in ordered:
        if day.weekday > weekday:
            return day
    return ordered[0]  # оборот на начало следующей недели
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/test_schedule.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add bukafit/core/schedule.py tests/test_schedule.py
git commit -m "feat: workout schedule (today / next)"
```

---

## Task 11: Стрики (чистая функция)

**Files:**
- Create: `bukafit/core/streaks.py`
- Test: `tests/test_streaks.py`

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_streaks.py
from datetime import date

from bukafit.core.streaks import current_streak


def test_empty():
    assert current_streak([], today=date(2026, 6, 23)) == 0


def test_today_only():
    assert current_streak([date(2026, 6, 23)], today=date(2026, 6, 23)) == 1


def test_consecutive_days():
    dates = [date(2026, 6, 21), date(2026, 6, 22), date(2026, 6, 23)]
    assert current_streak(dates, today=date(2026, 6, 23)) == 3


def test_gap_breaks_streak():
    dates = [date(2026, 6, 20), date(2026, 6, 22), date(2026, 6, 23)]
    assert current_streak(dates, today=date(2026, 6, 23)) == 2


def test_streak_counts_from_yesterday_if_no_today():
    dates = [date(2026, 6, 21), date(2026, 6, 22)]
    assert current_streak(dates, today=date(2026, 6, 23)) == 2


def test_duplicates_collapse():
    dates = [date(2026, 6, 23), date(2026, 6, 23), date(2026, 6, 22)]
    assert current_streak(dates, today=date(2026, 6, 23)) == 2
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_streaks.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'bukafit.core.streaks'`

- [ ] **Step 3: Реализовать `bukafit/core/streaks.py`**

```python
from datetime import date, timedelta


def current_streak(dates: list[date], today: date) -> int:
    """Серия подряд идущих дней с тренировкой, считая от сегодня или вчера."""
    days = set(dates)
    if not days:
        return 0

    # старт: сегодня (если есть) иначе вчера (если есть) иначе серии нет
    if today in days:
        cursor = today
    elif (today - timedelta(days=1)) in days:
        cursor = today - timedelta(days=1)
    else:
        return 0

    streak = 0
    while cursor in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak
```

- [ ] **Step 4: Запустить тесты — должны пройти**

Run: `pytest tests/test_streaks.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add bukafit/core/streaks.py tests/test_streaks.py
git commit -m "feat: training streak calculation"
```

---

## Task 12: Прогон всего набора тестов

- [ ] **Step 1: Запустить все тесты**

Run: `. .venv/bin/activate && pytest -q`
Expected: PASS — все тесты зелёные (schemas + progression + schedule + streaks + repositories).

- [ ] **Step 2: Линт**

Run: `. .venv/bin/activate && ruff check bukafit tests`
Expected: `All checks passed!` (либо исправить замечания и повторить).

- [ ] **Step 3: Commit (если ruff что-то поправил)**

```bash
git add -A
git commit -m "chore: lint pass for foundation" || echo "nothing to commit"
```

---

## Definition of Done (План 1)

- [ ] `pytest -q` — всё зелёное.
- [ ] `docker compose up -d db redis` поднимает инфраструктуру.
- [ ] `alembic upgrade head` создаёт все 5 таблиц.
- [ ] Доменная логика (progression/schedule/streaks) покрыта тестами.
- [ ] Репозитории читают/пишут JSONB через Pydantic-схемы.
- [ ] Готово к Плану 2 (бот + ИИ-слой + напоминания).
