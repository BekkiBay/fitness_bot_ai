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
