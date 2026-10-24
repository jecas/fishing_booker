import subprocess
import sys
import unittest

from app import models
from app.db import Base, SessionLocal, engine


def clear_test_tables():
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


class DatabaseTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        if engine.dialect.name != "postgresql" or engine.url.host != "test-db" or engine.url.database != "booking_test":
            raise RuntimeError("Tests must use PostgreSQL test-db/booking_test.")

        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

    def setUp(self):
        super().setUp()

        clear_test_tables()

        self.session = SessionLocal()
        self.addCleanup(self.cleanup_database)

    def cleanup_database(self):
        try:
            self.session.rollback()
        finally:
            self.session.close()
            clear_test_tables()