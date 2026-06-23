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
