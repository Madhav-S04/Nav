import pytest
from datetime import datetime, timedelta, date, time
from backend.app.sla_engine import (
    is_working_day, is_during_working_hours, add_working_seconds,
    calculate_working_seconds_between, compute_sla_deadlines, evaluate_ticket_sla,
    WORK_START, WORK_END, DAILY_WORKING_SECONDS
)

def test_friday_6pm_ticket_not_late_on_sunday():
    """
    Requirement from Support Lead Meera:
    'If a ticket arrives at 6 PM on Friday, it should not be late on Sunday morning.
     Right now our spreadsheet says it is late.'
    """
    # Friday 2026-11-20 at 18:00 (6:00 PM)
    friday_6pm = datetime(2026, 11, 20, 18, 0, 0)
    
    # Deadlines for MEDIUM (reply SLA is 4.5 working hours = 16,200 seconds)
    deadlines = compute_sla_deadlines(friday_6pm, "MEDIUM")
    reply_deadline = deadlines["reply_deadline"]

    # 30 mins available on Friday (18:00 to 18:30)
    # Remaining 4 working hours will roll over to Monday 09:30 + 4 hours = Monday 13:30!
    assert reply_deadline == datetime(2026, 11, 23, 13, 30, 0), f"Expected Monday 13:30, got {reply_deadline}"

    # Sunday morning: 2026-11-22 at 10:00 AM
    sunday_morning = datetime(2026, 11, 22, 10, 0, 0)

    # Calculate working seconds elapsed between Friday 18:00 and Sunday morning
    elapsed_working_seconds = calculate_working_seconds_between(friday_6pm, sunday_morning)
    
    # Exactly 30 minutes (1800 seconds) of business time elapsed, because weekend is excluded!
    assert elapsed_working_seconds == 1800, f"Expected 1800s, got {elapsed_working_seconds}"

    # Verify SLA status on Sunday morning
    sla_eval = evaluate_ticket_sla(
        created_at=friday_6pm,
        severity="MEDIUM",
        status="OPEN",
        first_reply_deadline=reply_deadline,
        resolution_deadline=deadlines["resolution_deadline"],
        first_replied_at=None,
        resolved_at=None,
        total_paused_seconds=0.0,
        last_paused_at=None,
        current_time=sunday_morning
    )

    # It MUST NOT be late on Sunday morning!
    assert sla_eval["reply_late"] is False, "Ticket should NOT be late on Sunday morning!"
    assert sla_eval["reply_status"] in ("ON_TRACK", "PAUSED")


def test_urgent_ticket_slas():
    """
    'If a customer cannot work at all, we must reply within two hours, and fix it the same working day.'
    """
    # Tuesday 10:00 AM
    tuesday_10am = datetime(2026, 11, 24, 10, 0, 0)
    deadlines = compute_sla_deadlines(tuesday_10am, "URGENT")

    # Reply deadline: 2 working hours = Tuesday 12:00 PM
    assert deadlines["reply_deadline"] == datetime(2026, 11, 24, 12, 0, 0)

    # Resolution deadline: Same working day by 18:30
    assert deadlines["resolution_deadline"] == datetime(2026, 11, 24, 18, 30, 0)


def test_sla_pausing_when_waiting_on_customer():
    """
    'Sometimes we ask the customer a question, and then we wait for their answer.
     That waiting time still counts against us. That week is not our fault.'
    """
    # Ticket created Monday 10:00 AM
    created_at = datetime(2026, 11, 23, 10, 0, 0)
    deadlines = compute_sla_deadlines(created_at, "URGENT") # reply by 12:00 PM

    # Agent asked question at 11:00 AM, pausing the timer
    paused_at = datetime(2026, 11, 23, 11, 0, 0)

    # 3 days later, customer still hasn't answered
    current_time = datetime(2026, 11, 26, 11, 0, 0)

    sla_eval = evaluate_ticket_sla(
        created_at=created_at,
        severity="URGENT",
        status="WAITING_ON_CUSTOMER",
        first_reply_deadline=deadlines["reply_deadline"],
        resolution_deadline=deadlines["resolution_deadline"],
        first_replied_at=None,
        resolved_at=None,
        total_paused_seconds=0.0,
        last_paused_at=paused_at,
        current_time=current_time
    )

    # Because status is WAITING_ON_CUSTOMER, it must be marked PAUSED, not late!
    assert sla_eval["reply_status"] == "PAUSED"
    assert sla_eval["reply_late"] is False
    assert sla_eval["accumulated_paused_seconds"] > 0
