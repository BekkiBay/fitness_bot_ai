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
    markup = kb.log_kb("squat", 40.0)
    cbs = [b.callback_data for row in markup.inline_keyboard for b in row]
    assert any(c.startswith("log:squat:done:") for c in cbs)
    assert any(c.startswith("log:squat:skip:") for c in cbs)
    assert "log:squat:wup:40.0" in cbs
