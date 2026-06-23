from bukafit.ai import prompts
from bukafit.ai.provider import Memory
from bukafit.core.schemas import (
    DayPlan, ExercisePlan, Inventory, ProfileData, ProgramData,
)

WEEKDAY_TITLES = {1: "Понедельник", 2: "Вторник", 3: "Среда", 4: "Четверг",
                  5: "Пятница", 6: "Суббота", 7: "Воскресенье"}

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
