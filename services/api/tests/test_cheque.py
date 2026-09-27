from datetime import date

from nexus.india.cheque import add_months, rupees, rupees_in_words, timeline


def test_amounts_in_indian_style():
    assert rupees(450000) == "4,50,000"
    assert rupees(12345678) == "1,23,45,678"
    assert rupees(999) == "999"
    assert rupees_in_words(450000) == "Rupees Four Lakh Fifty Thousand only"
    assert rupees_in_words(12345678) == "Rupees One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight only"
    assert rupees_in_words(100) == "Rupees One Hundred only"
    assert rupees_in_words(5_00_00_00_000) == "Rupees Five Hundred Crore only"


def test_month_arithmetic_handles_month_ends():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2026, 11, 30), 3) == date(2027, 2, 28)


def test_timeline_in_time():
    t = timeline(cheque_date=date(2026, 1, 10), presented_on=date(2026, 2, 2),
                 information_received_on=date(2026, 2, 5), notice_sent_on=date(2026, 2, 20),
                 notice_served_on=date(2026, 2, 24))
    assert t.cheque_valid_until == date(2026, 4, 9)
    assert t.notice_last_day == date(2026, 3, 7)            # 30 days after 5 Feb
    assert t.payment_last_day == date(2026, 3, 11)          # 15 days after service
    assert t.cause_of_action == date(2026, 3, 12)
    assert t.complaint_last_day == date(2026, 4, 12)        # one month, excluding the first day
    assert all(c.ok for c in t.checks)


def test_timeline_flags_late_presentation_and_late_notice():
    t = timeline(cheque_date=date(2026, 1, 10), presented_on=date(2026, 4, 15),
                 information_received_on=date(2026, 4, 17), notice_sent_on=date(2026, 5, 20))
    titles = {c.title: c.ok for c in t.checks}
    assert titles["Cheque presented after its validity"] is False
    assert titles["Notice sent after the 30-day limit"] is False


def test_notice_not_yet_sent_shows_days_left():
    t = timeline(cheque_date=date(2026, 1, 10), presented_on=date(2026, 2, 2),
                 information_received_on=date(2026, 2, 5), today=date(2026, 2, 25))
    deadline = next(c for c in t.checks if c.title.startswith("Notice must be sent"))
    assert deadline.ok and "(10 days left)" in deadline.title
