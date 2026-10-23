from datetime import date

from app.db import SessionLocal
from app.models import Captains, CaptainDayOff


with SessionLocal() as session:
    with session.begin():
        captain = session.get(Captains, 1)

        if not captain:
            raise ValueError("Captain not found")

        day_off = CaptainDayOff(captain=captain, day=date(2027, 6, 15))
        session.add(day_off)

    print("Transaction committed.")