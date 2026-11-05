from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .auth import get_password_hash, verify_password
from .models import Cycle, User
from .schemas import CycleCreate, UserCreate


def register_user(db: Session, user_data: UserCreate) -> User:
    existing = (
        db.query(User)
        .filter(or_(User.email == user_data.email, User.username == user_data.username))
        .first()
    )
    if existing:
        raise ValueError("Un compte avec ce nom d'utilisateur ou cet email existe déjà.")

    user = User(
        username=user_data.username.strip(),
        email=str(user_data.email).lower(),
        password_hash=get_password_hash(user_data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, identifier: str, password: str) -> User | None:
    user = (
        db.query(User)
        .filter(or_(User.email == identifier.lower(), User.username == identifier))
        .first()
    )
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_user_cycles(db: Session, user_id: int) -> list[Cycle]:
    return (
        db.query(Cycle)
        .filter(Cycle.user_id == user_id)
        .order_by(Cycle.start_date.desc())
        .all()
    )


def create_cycle(db: Session, user_id: int, cycle_data: CycleCreate) -> Cycle:
    if cycle_data.end_date < cycle_data.start_date:
        raise ValueError("La date de fin doit être après la date de début.")

    cycle = Cycle(
        user_id=user_id,
        start_date=cycle_data.start_date,
        end_date=cycle_data.end_date,
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def calculate_average_cycle_length(db: Session, user_id: int) -> int:
    cycles = get_user_cycles(db, user_id)
    if len(cycles) < 2:
        return 28

    durations = []
    sorted_cycles = sorted(cycles, key=lambda cycle: cycle.start_date)
    for previous, current in zip(sorted_cycles, sorted_cycles[1:]):
        durations.append((current.start_date - previous.start_date).days)

    if not durations:
        return 28

    return int(round(sum(durations) / len(durations)))


def predict_next_period(db: Session, user_id: int) -> date | None:
    cycles = get_user_cycles(db, user_id)
    if not cycles:
        return None

    cycles_sorted = sorted(cycles, key=lambda cycle: cycle.start_date)
    average = calculate_average_cycle_length(db, user_id)
    last_cycle = cycles_sorted[-1]
    return last_cycle.start_date + timedelta(days=average)


def build_monthly_calendar(cycles: list[Cycle], month: date | None = None) -> dict:
    month_candidates = sorted({cycle.start_date.replace(day=1) for cycle in cycles})
    month_date = month or date.today().replace(day=1)

    if month is None:
        if month_candidates:
            most_recent_cycle_month = month_candidates[-1]
            current_month = date.today().replace(day=1)
            if not any(cycle.start_date.replace(day=1) == current_month for cycle in cycles):
                month_date = most_recent_cycle_month

    month_start = month_date.replace(day=1)
    year = month_start.year
    month_number = month_start.month
    last_day = monthrange(year, month_number)[1]
    month_last = date(year, month_number, last_day)

    period_dates = set()
    for cycle in cycles:
        cycle_start = cycle.start_date
        cycle_end = cycle.end_date
        if cycle_end < month_start:
            continue
        if cycle_start > month_last:
            continue

        range_start = max(cycle_start, month_start)
        range_end = min(cycle_end, month_last)
        current = range_start
        while current <= range_end:
            period_dates.add(current.isoformat())
            current += timedelta(days=1)

    days = []
    for day in range(1, last_day + 1):
        current_day = date(year, month_number, day)
        days.append(
            {
                "day": day,
                "date": current_day.isoformat(),
                "is_period": current_day.isoformat() in period_dates,
            }
        )

    return {
        "month": month_start.strftime("%Y-%m"),
        "period_dates": sorted(period_dates),
        "days": days,
    }


def get_dashboard_data(db: Session, user_id: int) -> dict:
    cycles = get_user_cycles(db, user_id)
    today = date.today()
    average_cycle_length = calculate_average_cycle_length(db, user_id)

    current_cycle = None
    if cycles:
        last_cycle = sorted(cycles, key=lambda cycle: cycle.start_date)[-1]
        start = last_cycle.start_date
        end = last_cycle.end_date
        if start <= today <= end:
            current_cycle = {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "status": "Cycle actuel en cours",
                "days_elapsed": (today - start).days + 1,
                "days_remaining": (end - today).days,
            }
        else:
            current_cycle = {
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "status": "Dernier cycle enregistré",
                "days_elapsed": (end - start).days + 1,
                "days_remaining": 0,
            }

    next_period = predict_next_period(db, user_id)
    return {
        "total_cycles": len(cycles),
        "average_cycle_length": average_cycle_length,
        "next_period_date": next_period.isoformat() if next_period else None,
        "current_cycle": current_cycle,
        "calendar": build_monthly_calendar(cycles),
        "history": [
            {
                "id": cycle.id,
                "start_date": cycle.start_date.isoformat(),
                "end_date": cycle.end_date.isoformat(),
                "duration_days": (cycle.end_date - cycle.start_date).days + 1,
            }
            for cycle in sorted(cycles, key=lambda cycle: cycle.start_date, reverse=True)
        ],
    }
