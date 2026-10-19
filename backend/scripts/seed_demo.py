"""Seed a demo tenant with rich, realistic data.

The dataset is a rolling eight-month story anchored to the day it runs, so
a freshly seeded demo always looks current:

* two household members (Alex Rivera, owner; Maya Rivera, member) so the
  Members tab shows a real roster, not just pending invites;
* eleven expense categories and four income ones, all actively used;
* recurring bills on fixed days (rent, utilities, subscriptions), weekly
  rhythms (groceries, fuel, coffee) and story months — a trip, a dentist
  bill, a car repair — that make the reports worth reading;
* the current month runs up to today and lands slightly over budget, so
  the pace line, alert badge and category breakdown all have meaning.

Boot behaviour is unchanged: runs automatically when SEED_DEMO=true and
the database has no tenants. To wipe and rebuild the demo tenant at any
time:

    docker compose exec backend python -m scripts.seed_demo --force

Demo credentials (change or delete before going live):
    workspace slug: demo
    owner:          demo@example.com / Demo@12345  (Alex Rivera)
    member:         maya@example.com / Demo@12345  (Maya Rivera)
"""

from __future__ import annotations

import argparse
import asyncio
import random
from calendar import monthrange
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal, engine, set_tenant_context
from app.core.security import hash_password
from app.models import (
    AuditLog,
    Budget,
    Category,
    Expense,
    Income,
    Invite,
    RefreshToken,
    Tenant,
    User,
)

DEMO_SLUG = "demo"
DEMO_EMAIL = "demo@example.com"
DEMO_MEMBER_EMAIL = "maya@example.com"
DEMO_PASSWORD = "Demo@12345"

MONTHLY_BUDGET = Decimal("3150.00")
HISTORY_MONTHS = 8

# Richer than the registration defaults: every slice has data and every
# colour is distinct, which makes the reports and filters look great.
EXPENSE_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("Housing", "#2f6df6"),
    ("Groceries", "#16a34a"),
    ("Dining out", "#ef4444"),
    ("Coffee", "#b45309"),
    ("Transport", "#f59e0b"),
    ("Utilities", "#8b5cf6"),
    ("Subscriptions", "#06b6d4"),
    ("Health", "#ec4899"),
    ("Entertainment", "#a855f7"),
    ("Shopping", "#84cc16"),
    ("Travel", "#14b8a6"),
)
INCOME_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("Salary", "#16a34a"),
    ("Freelance", "#2f6df6"),
    ("Investments", "#8b5cf6"),
    ("Other income", "#64748b"),
)

# Story beats that give specific months a reason to look different.
FREELANCE_MONTHS: dict[int, Decimal] = {
    -6: Decimal("520.00"),
    -4: Decimal("650.00"),
    -2: Decimal("480.00"),
    -1: Decimal("380.00"),
}
DIVIDEND_MONTHS = (-5, -2)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def _amount(rng: random.Random, low: float, high: float) -> Decimal:
    return Decimal(f"{rng.uniform(low, high):.2f}")


def _populate_month(
    *,
    tenant: Tenant,
    owner: User,
    maya: User,
    rng: random.Random,
    delta: int,
    today: date,
    categories: dict[str, Category],
    income_categories: dict[str, Category],
    expenses: list[Expense],
    incomes: list[Income],
    budgets: list[Budget],
) -> None:
    year, month = _shift_month(today.year, today.month, delta)
    cap = today.day if delta == 0 else monthrange(year, month)[1]
    # The month before the SFO trip was a deliberate low-spend month;
    # it gives the reports a genuinely green bar and tells a story.
    frugal = delta == -(HISTORY_MONTHS - 1)

    def spend(
        day: int,
        category: Category | None,
        note: str,
        amount: Decimal,
        who: User | None = None,
    ) -> None:
        if day < 1 or day > cap:
            return
        expenses.append(
            Expense(
                tenant_id=tenant.id,
                category_id=category.id if category else None,
                amount=amount,
                note=note,
                happened_on=date(year, month, day),
                created_by=(who or owner).id,
            )
        )

    def earn(day: int, category: Category, note: str, amount: Decimal) -> None:
        if day < 1 or day > cap:
            return
        incomes.append(
            Income(
                tenant_id=tenant.id,
                category_id=category.id,
                amount=amount,
                note=note,
                happened_on=date(year, month, day),
                created_by=owner.id,
            )
        )

    def weekend_day() -> int:
        days = [d for d in range(1, cap + 1) if date(year, month, d).weekday() >= 4]
        return rng.choice(days) if days else rng.randint(1, cap)

    budgets.append(
        Budget(
            tenant_id=tenant.id,
            year=year,
            month=month,
            amount=MONTHLY_BUDGET,
            alert_threshold_pct=80,
        )
    )

    # Fixed bills land on the same days every month.
    spend(1, categories["Housing"], "Rent - Maple St", Decimal("1450.00"))
    spend(2, categories["Health"], "Gym membership", Decimal("45.00"), who=maya)
    spend(2, categories["Transport"], "TriMet monthly pass", Decimal("100.00"))
    spend(3, categories["Subscriptions"], "Netflix", Decimal("15.49"))
    spend(5, categories["Utilities"], "Electric bill", _amount(rng, 88, 126))
    spend(7, categories["Subscriptions"], "Spotify", Decimal("11.99"))
    spend(8, categories["Utilities"], "Internet - Fiberline", Decimal("65.00"))
    spend(10, categories["Utilities"], "Phone - Mobile plan", Decimal("48.00"))
    spend(12, categories["Subscriptions"], "iCloud+", Decimal("2.99"))
    spend(14, categories["Health"], "Pharmacy - prescriptions", _amount(rng, 12, 38), who=maya)
    if month % 2 == 0:
        spend(16, categories["Utilities"], "Water & sewer", _amount(rng, 38, 52))

    # Weekly rhythms: groceries, dining, coffee, fuel, errands.
    spend(weekend_day(), categories["Groceries"], "Farmers market", _amount(rng, 30, 52), who=maya)
    for name in ("Whole Foods", "Trader Joe's", "Safeway"):
        spend(
            rng.randint(1, cap),
            categories["Groceries"],
            name,
            _amount(rng, 42, 92),
            who=rng.choice((owner, maya)),
        )
    spend(rng.randint(min(10, cap), cap), categories["Groceries"], "Costco run", _amount(rng, 115, 160))

    if not frugal:
        for name in rng.sample(
            ["Dinner at Rosetta", "Sushi night", "Brunch - Sunny Cafe", "Pizza night", "Thai takeout"],
            rng.randint(3, 4),
        ):
            spend(
                weekend_day(),
                categories["Dining out"],
                name,
                _amount(rng, 24, 64),
                who=rng.choice((owner, maya)),
            )
        for name in rng.sample(
            ["Starbucks", "Blue Bottle", "Stumptown Coffee", "Little T Baker"], rng.randint(3, 4)
        ):
            spend(
                rng.randint(1, cap),
                categories["Coffee"],
                name,
                _amount(rng, 4.25, 7.75),
                who=rng.choice((owner, maya)),
            )

    spend(rng.randint(1, cap), categories["Coffee"], "Coffee beans - Stumptown", Decimal("17.50"))

    spend(rng.randint(1, cap), categories["Transport"], "Shell", _amount(rng, 40, 54))
    spend(rng.randint(1, cap), categories["Transport"], "Chevron", _amount(rng, 38, 52))
    if not frugal and rng.random() < 0.7:
        spend(weekend_day(), categories["Transport"], "Uber", _amount(rng, 10, 24))

    if not frugal:
        spend(weekend_day(), categories["Entertainment"], "Movie night", _amount(rng, 26, 38))
        spend(
            rng.randint(1, cap),
            categories["Shopping"],
            "Target run",
            _amount(rng, 34, 82),
            who=rng.choice((owner, maya)),
        )
        spend(rng.randint(1, cap), categories["Shopping"], "Amazon order", _amount(rng, 16, 56))

        # One uncategorised cash withdrawal a month keeps the
        # "Uncategorized" filter and report slice meaningful.
        spend(rng.randint(1, cap), None, "ATM withdrawal", Decimal("60.00"))

    # Income: salary lands on the 1st and the 15th.
    earn(1, income_categories["Salary"], "Salary - 1st half", Decimal("2100.00"))
    earn(15, income_categories["Salary"], "Salary - 2nd half", Decimal("2100.00"))
    if delta in FREELANCE_MONTHS:
        earn(rng.randint(12, 24), income_categories["Freelance"], "Design consulting invoice", FREELANCE_MONTHS[delta])
    if delta in DIVIDEND_MONTHS:
        earn(20, income_categories["Investments"], "Dividend payout", _amount(rng, 60, 120))

    # Story months.
    if delta == -6:
        spend(9, categories["Travel"], "Flight - SFO trip", Decimal("242.00"))
        spend(10, categories["Travel"], "Hotel - 2 nights", Decimal("356.00"))
    elif delta == -5:
        spend(
            weekend_day(),
            categories["Entertainment"],
            "Concert tickets - The War on Drugs",
            Decimal("120.00"),
        )
    elif delta == -4:
        spend(17, categories["Health"], "Dentist - crown", Decimal("300.00"))
    elif delta == -3:
        spend(weekend_day(), categories["Travel"], "Weekend cabin rental", Decimal("290.00"))
        spend(weekend_day(), categories["Transport"], "Gas - road trip", Decimal("48.00"))
    elif delta == -1:
        spend(11, categories["Shopping"], "New running shoes", Decimal("119.95"))
        spend(21, categories["Shopping"], "IKEA - desk & chair", Decimal("230.00"))
    elif delta == 0:
        # The month the car needed brakes: nudges the current month over
        # budget partway through, so the alert states have something to say.
        spend(14, categories["Transport"], "Car repair - brakes & rotors", Decimal("440.00"))
        earn(12, income_categories["Freelance"], "Design consulting invoice", Decimal("450.00"))

    if delta == 0:
        # Make the very latest transactions tell a nice story on the
        # dashboard's recent-expenses panel.
        spend(cap - 3, categories["Transport"], "Shell", Decimal("48.30"), who=maya)
        spend(cap - 2, categories["Dining out"], "Dinner at Rosetta", Decimal("78.40"))
        spend(cap - 1, categories["Coffee"], "Blue Bottle", Decimal("6.25"))


async def _populate(session: AsyncSession, tenant: Tenant) -> tuple[int, int]:
    rng = random.Random(42)
    today = date.today()

    owner = User(
        tenant_id=tenant.id,
        email=DEMO_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name="Alex Rivera",
        role="owner",
    )
    maya = User(
        tenant_id=tenant.id,
        email=DEMO_MEMBER_EMAIL,
        password_hash=hash_password(DEMO_PASSWORD),
        full_name="Maya Rivera",
        role="member",
    )
    session.add_all([owner, maya])
    await session.flush()

    categories: dict[str, Category] = {}
    for name, color in EXPENSE_CATEGORIES:
        category = Category(tenant_id=tenant.id, name=name, kind="expense", color=color)
        session.add(category)
        categories[name] = category
    income_categories: dict[str, Category] = {}
    for name, color in INCOME_CATEGORIES:
        category = Category(tenant_id=tenant.id, name=name, kind="income", color=color)
        session.add(category)
        income_categories[name] = category
    await session.flush()

    expenses: list[Expense] = []
    incomes: list[Income] = []
    budgets: list[Budget] = []
    for delta in range(-(HISTORY_MONTHS - 1), 1):
        _populate_month(
            tenant=tenant,
            owner=owner,
            maya=maya,
            rng=rng,
            delta=delta,
            today=today,
            categories=categories,
            income_categories=income_categories,
            expenses=expenses,
            incomes=incomes,
            budgets=budgets,
        )

    session.add_all([*budgets, *incomes, *expenses])
    await session.flush()
    return len(expenses), len(incomes)


async def _wipe(session: AsyncSession, tenant: Tenant) -> None:
    await set_tenant_context(session, tenant.id)
    for model in (Expense, Income, Invite, RefreshToken, Budget, AuditLog, Category, User):
        await session.execute(delete(model).where(model.tenant_id == tenant.id))


async def _seed(session: AsyncSession, *, force: bool) -> bool:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.slug == DEMO_SLUG))
    ).scalar_one_or_none()

    if tenant is None:
        tenant = Tenant(slug=DEMO_SLUG, name="Demo Workspace")
        session.add(tenant)
        await session.flush()
    elif force:
        await _wipe(session, tenant)
    else:
        return False

    tenant.name = "Demo Workspace"
    tenant.tier = "pro"
    tenant.status = "active"
    tenant.currency = "USD"
    tenant.locale = "en-US"
    tenant.timezone = "America/Los_Angeles"
    tenant.branding = {"display_name": "Demo Budget", "accent_color": "#2f6df6"}

    await set_tenant_context(session, tenant.id)
    await _populate(session, tenant)
    return True


async def seed_if_empty() -> bool:
    """Create the demo tenant if the database has no tenants yet."""
    async with SessionLocal() as session:
        async with session.begin():
            tenant_count = (
                await session.execute(select(func.count()).select_from(Tenant))
            ).scalar_one()
            if tenant_count > 0:
                return False
            return await _seed(session, force=False)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the demo tenant.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="wipe the existing demo tenant's data and rebuild it",
    )
    args = parser.parse_args()

    if args.force:
        async with SessionLocal() as session:
            async with session.begin():
                await _seed(session, force=True)
        print(f"Re-seeded demo tenant '{DEMO_SLUG}' (owner {DEMO_EMAIL}, member {DEMO_MEMBER_EMAIL})")
    else:
        created = await seed_if_empty()
        if created:
            print(f"Seeded demo tenant '{DEMO_SLUG}' with owner {DEMO_EMAIL}")
        else:
            print("Database already has tenants; nothing to seed. Use --force to rebuild the demo.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
