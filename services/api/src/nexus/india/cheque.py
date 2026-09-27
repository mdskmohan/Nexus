"""Section 138, Negotiable Instruments Act, 1881: the statutory timeline.

Computed in code, never by the AI, because a notice sent a day late or a
complaint filed a day late can defeat the client's case.

The rules applied (each shown to the lawyer with its source):
  * the cheque must be presented within its validity: three months from the
    date of the cheque (RBI instruction, effective 1 April 2012), within the
    six-month outer limit of s.138 proviso (a);
  * the demand notice must be made in writing within 30 days of the payee
    receiving information of dishonour from the bank (proviso (b));
  * the offence is complete if the drawer does not pay within 15 days of
    receiving the notice (proviso (c));
  * the complaint must be filed within one month of the date the cause of
    action arises (s.142(1)(b)); the day the cause of action arises is
    excluded (Saketh India Ltd v India Securities Ltd, (1999) 3 SCC 1).

Computed dates are the latest dates on a strict reading. Lawyers should
still act well before them.
"""

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


@dataclass
class Check:
    ok: bool
    title: str
    detail: str
    source: str


@dataclass
class Timeline:
    cheque_valid_until: date
    notice_last_day: date
    payment_last_day: date | None = None     # needs the date the drawer received the notice
    cause_of_action: date | None = None
    complaint_last_day: date | None = None
    checks: list[Check] = field(default_factory=list)


def timeline(cheque_date: date, presented_on: date, information_received_on: date,
             notice_sent_on: date | None = None, notice_served_on: date | None = None,
             today: date | None = None) -> Timeline:
    today = today or date.today()
    valid_until = add_months(cheque_date, 3) - timedelta(days=1)
    notice_last = information_received_on + timedelta(days=30)
    t = Timeline(valid_until, notice_last)

    t.checks.append(Check(
        presented_on <= valid_until,
        "Cheque presented within its validity" if presented_on <= valid_until
        else "Cheque presented after its validity",
        f"Dated {fmt(cheque_date)}, valid for three months (until {fmt(valid_until)}); presented {fmt(presented_on)}.",
        "s.138 proviso (a); RBI instruction on cheque validity (from 1 April 2012)",
    ))
    if presented_on < cheque_date:
        t.checks.append(Check(False, "Presented before the date on the cheque",
                              "A post-dated cheque presented early is not a valid presentation.", "s.138"))
    if information_received_on < presented_on:
        t.checks.append(Check(False, "Dates out of order",
                              "The bank's information of dishonour cannot come before presentation.", "—"))

    if notice_sent_on:
        in_time = notice_sent_on <= notice_last
        t.checks.append(Check(
            in_time,
            "Notice sent within 30 days" if in_time else "Notice sent after the 30-day limit",
            f"Information of dishonour received {fmt(information_received_on)}; last day for the notice "
            f"{fmt(notice_last)}; sent {fmt(notice_sent_on)}.",
            "s.138 proviso (b)",
        ))
    else:
        days_left = (notice_last - today).days
        t.checks.append(Check(
            days_left >= 0,
            f"Notice must be sent by {fmt(notice_last)}" + (f" ({days_left} days left)" if days_left >= 0 else ""),
            "The demand notice must be sent within 30 days of receiving information of dishonour from the bank."
            + ("" if days_left >= 0 else " That date has passed."),
            "s.138 proviso (b)",
        ))

    if notice_served_on:
        t.payment_last_day = notice_served_on + timedelta(days=15)
        t.cause_of_action = t.payment_last_day + timedelta(days=1)
        t.complaint_last_day = add_months(t.cause_of_action, 1)
        t.checks.append(Check(
            True, f"Complaint to be filed by {fmt(t.complaint_last_day)}",
            f"Notice served {fmt(notice_served_on)}; the drawer had until {fmt(t.payment_last_day)} to pay; "
            f"cause of action arises {fmt(t.cause_of_action)}; one month from then, excluding that day.",
            "s.138 proviso (c); s.142(1)(b); Saketh India v India Securities (1999) 3 SCC 1",
        ))
    return t


def fmt(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


# Amounts, Indian style ----------------------------------------------------

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else ""))


def _three(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = [f"{_ONES[hundreds]} Hundred"] if hundreds else []
    if rest:
        parts.append(_two(rest))
    return " ".join(parts)


def rupees_in_words(amount: int) -> str:
    """4,50,000 -> 'Rupees Four Lakh Fifty Thousand only'."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    crore, rest = divmod(amount, 10_000_000)
    lakh, rest = divmod(rest, 100_000)
    thousand, rest = divmod(rest, 1000)
    parts = []
    if crore:
        parts.append(f"{rupees_in_words(crore)[7:-5]} Crore" if crore >= 100 else f"{_two(crore)} Crore")
    if lakh:
        parts.append(f"{_two(lakh)} Lakh")
    if thousand:
        parts.append(f"{_two(thousand)} Thousand")
    if rest:
        parts.append(_three(rest))
    return "Rupees " + " ".join(parts) + " only"


def rupees(amount: int) -> str:
    """4500000 -> '45,00,000' (Indian digit grouping)."""
    s = str(amount)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail
