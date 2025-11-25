from utils.recurrence import normalize_recurrence_value


def test_known_keywords():
    assert normalize_recurrence_value("daily") == "daily"
    assert normalize_recurrence_value("Bi-Weekly") == "bi-weekly"


def test_interval_values():
    assert normalize_recurrence_value("9 days") == "every 9 days"
    assert normalize_recurrence_value("Every 14 days") == "every 14 days"


def test_weekday_ordinals():
    assert normalize_recurrence_value("First Saturday") == "first saturday"
    assert normalize_recurrence_value("last Friday") == "last friday"


def test_rejects_invalid_patterns():
    assert normalize_recurrence_value("sometimes") is None
    assert normalize_recurrence_value("every zero days") is None
