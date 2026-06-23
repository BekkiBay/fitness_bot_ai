from datetime import date, timedelta


def current_streak(dates: list[date], today: date) -> int:
    """Серия подряд идущих дней с тренировкой, считая от сегодня или вчера."""
    days = set(dates)
    if not days:
        return 0

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
