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
            return await self._fallback.generate_plan(profile)

    async def answer_question(self, question: str, memory: Memory) -> str:
        try:
            return (await self._run(prompts.qa_prompt(question, memory))).strip()
        except Exception:
            return await self._fallback.answer_question(question, memory)
