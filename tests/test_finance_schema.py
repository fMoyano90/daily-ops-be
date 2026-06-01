from datetime import date
from decimal import Decimal

from app.schemas.finance import FinanceEntryUpdate


def test_finance_entry_update_accepts_date_string():
    update = FinanceEntryUpdate(
        date="2026-05-31",
        type="expense",
        amount=Decimal("6180.00"),
        category="Pasajes Ninos",
    )

    assert update.date == date(2026, 5, 31)
