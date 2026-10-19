"""Budget Management System — OOP + menu-driven CLI edition.

This is the original educational version of the project: plain Python,
no dependencies, a single file. Run it with:

    python cli/budget_system.py

The SaaS version under backend/ + frontend/ is the productised evolution
of the same idea.
"""

from __future__ import annotations


class Expense:
    """A single spending record."""

    _next_id = 1

    def __init__(self, name: str, category: str, amount: float) -> None:
        self.eid = Expense._next_id
        Expense._next_id += 1
        self.name = name
        self.category = category
        self.amount = float(amount)

    def display(self) -> str:
        return f"[{self.eid:>3}] {self.name:<24} {self.category:<14} {self.amount:>12,.2f}"


class BudgetManagementSystem:
    """Tracks a monthly budget and the expenses recorded against it."""

    def __init__(self) -> None:
        self.budget: float = 0.0
        self.expenses: list[Expense] = []

    # ------------------------------------------------------------------ core
    def set_budget(self, amount: float) -> None:
        if amount < 0:
            raise ValueError("Budget cannot be negative.")
        self.budget = float(amount)

    def add_expense(self, name: str, category: str, amount: float) -> Expense:
        if amount <= 0:
            raise ValueError("Expense amount must be positive.")
        expense = Expense(name, category, amount)
        self.expenses.append(expense)
        return expense

    def delete_expense(self, eid: int) -> bool:
        for index, expense in enumerate(self.expenses):
            if expense.eid == eid:
                del self.expenses[index]
                return True
        return False

    # --------------------------------------------------------------- reports
    def total_expenses(self) -> float:
        return sum(expense.amount for expense in self.expenses)

    def remaining_budget(self) -> float:
        return self.budget - self.total_expenses()

    def budget_report(self) -> str:
        lines = [
            "=" * 62,
            f"  Budget        : {self.budget:>12,.2f}",
            f"  Total spent   : {self.total_expenses():>12,.2f}",
            f"  Remaining     : {self.remaining_budget():>12,.2f}",
            "=" * 62,
        ]
        if not self.expenses:
            lines.append("  No expenses recorded yet.")
        else:
            by_category: dict[str, float] = {}
            for expense in self.expenses:
                by_category[expense.category] = by_category.get(expense.category, 0.0) + expense.amount
            lines.append("  Spending by category:")
            for category, amount in sorted(by_category.items(), key=lambda item: -item[1]):
                share = (amount / self.budget * 100) if self.budget else 0.0
                lines.append(f"    - {category:<16} {amount:>12,.2f}  ({share:5.1f}% of budget)")
        if self.budget and self.total_expenses() > self.budget:
            lines.append("  !! You are OVER budget.")
        elif self.budget and self.total_expenses() >= 0.8 * self.budget:
            lines.append("  !  You have used 80% or more of the budget.")
        return "\n".join(lines)

    def view_expenses(self) -> str:
        if not self.expenses:
            return "  No expenses recorded yet."
        header = f"{'ID':>5}  {'Name':<24} {'Category':<14} {'Amount':>12}"
        rows = [expense.display() for expense in self.expenses]
        return "\n".join([header, "-" * 62, *rows])


# ---------------------------------------------------------------- menu loop
def _prompt_float(prompt: str) -> float | None:
    raw = input(prompt).strip()
    try:
        return float(raw)
    except ValueError:
        print("  Please enter a valid number.")
        return None


def main() -> None:
    system = BudgetManagementSystem()
    menu = """
=========== Budget Management System ===========
 1. Set monthly budget
 2. Add expense
 3. View all expenses
 4. Show total expenses
 5. Show remaining budget
 6. Show budget report
 7. Delete an expense
 8. Exit
=================================================
"""
    print("Welcome to the Budget Management System!")
    while True:
        print(menu)
        choice = input("Choose an option (1-8): ").strip()

        if choice == "1":
            amount = _prompt_float("  Enter monthly budget: ")
            if amount is not None:
                try:
                    system.set_budget(amount)
                    print(f"  Budget set to {system.budget:,.2f}.")
                except ValueError as error:
                    print(f"  {error}")

        elif choice == "2":
            name = input("  Expense name: ").strip()
            category = input("  Category: ").strip() or "General"
            amount = _prompt_float("  Amount: ")
            if name and amount is not None:
                try:
                    expense = system.add_expense(name, category, amount)
                    print(f"  Added expense #{expense.eid}.")
                except ValueError as error:
                    print(f"  {error}")

        elif choice == "3":
            print(system.view_expenses())

        elif choice == "4":
            print(f"  Total expenses: {system.total_expenses():,.2f}")

        elif choice == "5":
            print(f"  Remaining budget: {system.remaining_budget():,.2f}")

        elif choice == "6":
            print(system.budget_report())

        elif choice == "7":
            raw = input("  Expense ID to delete: ").strip()
            if raw.isdigit() and system.delete_expense(int(raw)):
                print("  Expense deleted.")
            else:
                print("  No expense with that ID.")

        elif choice == "8":
            print("Goodbye!")
            break

        else:
            print("  Invalid choice — enter a number from 1 to 8.")


if __name__ == "__main__":
    main()
