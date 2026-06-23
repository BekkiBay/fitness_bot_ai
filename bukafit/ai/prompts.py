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
