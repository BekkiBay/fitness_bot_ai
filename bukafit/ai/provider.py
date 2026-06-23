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
