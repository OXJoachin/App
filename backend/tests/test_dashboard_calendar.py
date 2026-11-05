import unittest
from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.crud import get_dashboard_data
from backend.app.database import Base
from backend.app.models import Cycle, User


class DashboardCalendarTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.user = User(username="alice", email="alice@example.com", password_hash="hash")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

        cycle1 = Cycle(user_id=self.user.id, start_date=date(2026, 9, 1), end_date=date(2026, 9, 5))
        cycle2 = Cycle(user_id=self.user.id, start_date=date(2026, 10, 1), end_date=date(2026, 10, 5))
        self.db.add_all([cycle1, cycle2])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    def test_dashboard_includes_average_length_and_calendar(self):
        dashboard = get_dashboard_data(self.db, self.user.id)

        self.assertEqual(dashboard["average_cycle_length"], 30)
        self.assertIn("calendar", dashboard)
        self.assertIn("period_dates", dashboard["calendar"])
        self.assertIn("2026-10-01", dashboard["calendar"]["period_dates"])


if __name__ == "__main__":
    unittest.main()
