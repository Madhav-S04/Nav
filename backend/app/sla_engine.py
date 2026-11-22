"""
Business Hours & SLA Engine for Frontdesk (Arvo Systems).

Rules from Support Lead Meera:
- Business Hours: 9:30 AM to 6:30 PM (09:30 - 18:30), Monday to Friday (9 hours/day = 540 mins/day).
- Non-working: Weekends (Saturday, Sunday) and Festival Holidays.
- Example: A ticket arriving at 6:00 PM on Friday has only 30 working minutes before 6:30 PM Friday.
  Over Saturday and Sunday, 0 working minutes elapse. On Monday at 9:30 AM, elapsed working time is still 30 minutes!
  It is NOT late on Sunday morning.

SLAs:
1. Urgent ("Cannot work at all"):
   - First Reply: within 2 working hours (120 working minutes)
   - Resolution: same working day (by 18:30 of that working day, or next working day 18:30 if created after-hours)
2. Medium:
   - First Reply: within half a day = 4.5 working hours (270 working minutes)
   - Resolution: about 3 working days = 27 working hours (1620 working minutes)
3. Small ("Questions or small requests"):
   - First Reply: within 1 working day = 9 working hours (540 working minutes)
   - Resolution: about 1 working week = 5 working days = 45 working hours (2700 working minutes)

Customer Waiting Time:
- Pauses the SLA clock while in WAITING_ON_CUSTOMER.
- Auto-close: If ticket remains in WAITING_ON_CUSTOMER for 1 working week (45 working hours = 2700 working minutes), auto-close.

Reopening Done Tickets:
- Customers can reopen a ticket within 7 calendar days of being marked RESOLVED.
- After 7 days, reopening is rejected (must create a new ticket).
"""

from datetime import datetime, date, time, timedelta
from typing import Dict, Any, Optional, List

# Standard Festival Holidays for 2026 (YYYY-MM-DD)
DEFAULT_HOLIDAYS = {
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 26),  # Republic Day
    date(2026, 3, 4),   # Holi
    date(2026, 4, 3),   # Good Friday
    date(2026, 4, 14),  # Vishu / Tamil New Year
    date(2026, 5, 1),   # May Day
    date(2026, 8, 15),  # Independence Day
    date(2026, 8, 27),  # Onam
    date(2026, 10, 2),  # Gandhi Jayanti
    date(2026, 10, 20), # Dussehra / Vijayadashami
    date(2026, 11, 8),  # Diwali
    date(2026, 12, 25), # Christmas
}

WORK_START = time(9, 30, 0)
WORK_END = time(18, 30, 0)
DAILY_WORKING_SECONDS = 9 * 3600  # 9 hours = 32,400 seconds

# SLA Definitions in working seconds
SLA_TARGETS = {
    "URGENT": {
        "reply_seconds": 2 * 3600,             # 2 working hours
        "resolve_same_day": True,               # By 18:30 of current/next business day
        "resolve_seconds": 9 * 3600,            # 1 working day fallback
    },
    "MEDIUM": {
        "reply_seconds": 4.5 * 3600,           # 4.5 working hours (half day)
        "resolve_same_day": False,
        "resolve_seconds": 3 * DAILY_WORKING_SECONDS, # 3 working days = 27 working hours
    },
    "SMALL": {
        "reply_seconds": 1 * DAILY_WORKING_SECONDS,   # 1 working day = 9 working hours
        "resolve_same_day": False,
        "resolve_seconds": 5 * DAILY_WORKING_SECONDS, # 1 working week = 45 working hours
    }
}

AUTO_CLOSE_WORKING_SECONDS = 5 * DAILY_WORKING_SECONDS  # 1 working week in WAITING_ON_CUSTOMER
REOPEN_WINDOW_DAYS = 7  # 1 calendar week for customer reopen window


def is_working_day(d: date, holidays: Optional[set] = None) -> bool:
    """Returns True if day is Monday through Friday and not a festival holiday."""
    if holidays is None:
        holidays = DEFAULT_HOLIDAYS
    if d.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return False
    if d in holidays:
        return False
    return True


def is_during_working_hours(dt: datetime, holidays: Optional[set] = None) -> bool:
    """Returns True if dt falls strictly within business working hours."""
    if not is_working_day(dt.date(), holidays):
        return False
    return WORK_START <= dt.time() <= WORK_END


def get_next_work_day_start(d: date, holidays: Optional[set] = None) -> datetime:
    """Finds the next working day start (9:30 AM) on or after date d."""
    current = d
    while not is_working_day(current, holidays):
        current += timedelta(days=1)
    return datetime.combine(current, WORK_START)


def advance_to_working_time(dt: datetime, holidays: Optional[set] = None) -> datetime:
    """
    If dt is outside working hours, snaps forward to the next valid working moment.
    """
    d = dt.date()
    t = dt.time()

    if not is_working_day(d, holidays):
        return get_next_work_day_start(d + timedelta(days=1), holidays)
    
    if t < WORK_START:
        return datetime.combine(d, WORK_START)
    elif t > WORK_END:
        return get_next_work_day_start(d + timedelta(days=1), holidays)
    
    return dt


def add_working_seconds(start_dt: datetime, seconds_to_add: float, holidays: Optional[set] = None) -> datetime:
    """
    Adds a given number of working seconds to start_dt, stepping strictly through business hours.
    Skips nights, weekends, and holidays.
    """
    if seconds_to_add <= 0:
        return start_dt

    current = advance_to_working_time(start_dt, holidays)
    remaining_seconds = float(seconds_to_add)

    while remaining_seconds > 0:
        day_end = datetime.combine(current.date(), WORK_END)
        available_today = (day_end - current).total_seconds()

        if remaining_seconds <= available_today:
            return current + timedelta(seconds=remaining_seconds)
        else:
            remaining_seconds -= available_today
            # Advance to start of next working day
            current = get_next_work_day_start(current.date() + timedelta(days=1), holidays)

    return current


def calculate_working_seconds_between(start_dt: datetime, end_dt: datetime, holidays: Optional[set] = None) -> float:
    """
    Calculates the exact number of business working seconds elapsed between start_dt and end_dt.
    Excludes weekends, nights, and holidays.
    """
    if end_dt <= start_dt:
        return 0.0

    current = advance_to_working_time(start_dt, holidays)
    if current >= end_dt:
        return 0.0

    total_seconds = 0.0

    while current < end_dt:
        # If current is on a non-working day, advance
        if not is_working_day(current.date(), holidays):
            current = get_next_work_day_start(current.date() + timedelta(days=1), holidays)
            if current >= end_dt:
                break

        day_end = datetime.combine(current.date(), WORK_END)
        day_start = datetime.combine(current.date(), WORK_START)

        # Make sure current is not before WORK_START
        if current < day_start:
            current = day_start

        if end_dt <= day_end:
            # Both inside today's window
            total_seconds += max(0.0, (end_dt - current).total_seconds())
            break
        else:
            # Up to end of today's business day
            total_seconds += max(0.0, (day_end - current).total_seconds())
            # Advance to start of next working day
            current = get_next_work_day_start(current.date() + timedelta(days=1), holidays)

    return total_seconds


def compute_sla_deadlines(created_at: datetime, severity: str, holidays: Optional[set] = None) -> Dict[str, datetime]:
    """
    Computes initial reply_deadline and resolution_deadline for a ticket based on severity.
    """
    sev = severity.upper()
    sla = SLA_TARGETS.get(sev, SLA_TARGETS["MEDIUM"])

    # Reply deadline is always add_working_seconds
    reply_deadline = add_working_seconds(created_at, sla["reply_seconds"], holidays)

    # Resolution deadline:
    if sla.get("resolve_same_day"):
        # Urgent: Same working day by 18:30
        effective_start = advance_to_working_time(created_at, holidays)
        resolution_deadline = datetime.combine(effective_start.date(), WORK_END)
    else:
        resolution_deadline = add_working_seconds(created_at, sla["resolve_seconds"], holidays)

    return {
        "reply_deadline": reply_deadline,
        "resolution_deadline": resolution_deadline,
    }


def evaluate_ticket_sla(
    created_at: datetime,
    severity: str,
    status: str,
    first_reply_deadline: datetime,
    resolution_deadline: datetime,
    first_replied_at: Optional[datetime],
    resolved_at: Optional[datetime],
    total_paused_seconds: float,
    last_paused_at: Optional[datetime],
    current_time: Optional[datetime] = None,
    holidays: Optional[set] = None
) -> Dict[str, Any]:
    """
    Evaluates the live SLA status of a ticket, taking into account:
    - Business hours
    - Paused time while waiting on customer
    - Whether reply / resolution already occurred
    - Deadlines adjusted for customer paused time
    """
    if current_time is None:
        current_time = datetime.utcnow()

    # If ticket is currently waiting on customer, compute active pause duration
    current_pause_seconds = 0.0
    if status == "WAITING_ON_CUSTOMER" and last_paused_at is not None:
        current_pause_seconds = calculate_working_seconds_between(last_paused_at, current_time, holidays)

    accumulated_paused = total_paused_seconds + current_pause_seconds

    # Effective deadlines are pushed back by accumulated paused seconds
    effective_reply_deadline = add_working_seconds(first_reply_deadline, accumulated_paused, holidays)
    effective_resolve_deadline = add_working_seconds(resolution_deadline, accumulated_paused, holidays)

    # 1. First Reply Evaluation
    if first_replied_at is not None:
        # Already replied: compare actual reply time against deadline at that point
        # (subtract paused seconds up to reply time)
        reply_working_elapsed = calculate_working_seconds_between(created_at, first_replied_at, holidays) - total_paused_seconds
        reply_working_elapsed = max(0.0, reply_working_elapsed)
        target_reply_seconds = SLA_TARGETS.get(severity.upper(), SLA_TARGETS["MEDIUM"])["reply_seconds"]
        
        reply_late = first_replied_at > effective_reply_deadline
        reply_status = "BREACHED" if reply_late else "FULFILLED"
        reply_remaining_seconds = 0.0
    else:
        # Not yet replied
        if status == "WAITING_ON_CUSTOMER":
            reply_status = "PAUSED"
            reply_late = False
            # Remaining working seconds till effective deadline
            reply_remaining_seconds = calculate_working_seconds_between(current_time, effective_reply_deadline, holidays)
        else:
            if current_time > effective_reply_deadline:
                reply_status = "BREACHED"
                reply_late = True
                reply_remaining_seconds = -calculate_working_seconds_between(effective_reply_deadline, current_time, holidays)
            else:
                reply_late = False
                reply_remaining_seconds = calculate_working_seconds_between(current_time, effective_reply_deadline, holidays)
                # Warning if less than 30 mins remaining
                reply_status = "WARNING" if reply_remaining_seconds < 1800 else "ON_TRACK"

    # 2. Resolution Evaluation
    if resolved_at is not None or status in ("RESOLVED", "CLOSED"):
        eval_time = resolved_at if resolved_at is not None else current_time
        resolve_late = eval_time > effective_resolve_deadline
        resolve_status = "BREACHED" if resolve_late else "FULFILLED"
        resolve_remaining_seconds = 0.0
    else:
        if status == "WAITING_ON_CUSTOMER":
            resolve_status = "PAUSED"
            resolve_late = False
            resolve_remaining_seconds = calculate_working_seconds_between(current_time, effective_resolve_deadline, holidays)
        else:
            if current_time > effective_resolve_deadline:
                resolve_status = "BREACHED"
                resolve_late = True
                resolve_remaining_seconds = -calculate_working_seconds_between(effective_resolve_deadline, current_time, holidays)
            else:
                resolve_late = False
                resolve_remaining_seconds = calculate_working_seconds_between(current_time, effective_resolve_deadline, holidays)
                # Warning if less than 2 working hours remaining
                resolve_status = "WARNING" if resolve_remaining_seconds < 7200 else "ON_TRACK"

    # 3. Overall Ticket SLA State
    is_any_late = reply_late or resolve_late
    overall_sla_badge = "BREACHED" if is_any_late else ("PAUSED" if status == "WAITING_ON_CUSTOMER" else ("FULFILLED" if (status in ("RESOLVED", "CLOSED") and not is_any_late) else "ON_TRACK"))

    # 4. Check Auto-Close candidate (1 working week waiting on customer)
    can_auto_close = False
    if status == "WAITING_ON_CUSTOMER" and current_pause_seconds >= AUTO_CLOSE_WORKING_SECONDS:
        can_auto_close = True

    return {
        "reply_status": reply_status,
        "reply_late": reply_late,
        "reply_remaining_seconds": reply_remaining_seconds,
        "effective_reply_deadline": effective_reply_deadline.isoformat(),
        
        "resolve_status": resolve_status,
        "resolve_late": resolve_late,
        "resolve_remaining_seconds": resolve_remaining_seconds,
        "effective_resolve_deadline": effective_resolve_deadline.isoformat(),

        "overall_sla_badge": overall_sla_badge,
        "accumulated_paused_seconds": accumulated_paused,
        "can_auto_close": can_auto_close,
    }
