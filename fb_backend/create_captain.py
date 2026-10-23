from app.db import SessionLocal
from app.models import Captains


with SessionLocal() as session:
    with session.begin():
        captain = Captains(first_name="Petar", last_name="Petrovic",
                           email="petar@example.com", phone="+381641234567")
        session.add(captain)
        session.flush()

        print(f"Generated new captain with ID: {captain.id}")

    print("Transaction committed.")