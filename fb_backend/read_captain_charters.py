from app.db import SessionLocal
from app.models import Captains


with SessionLocal() as session:
    captain = session.get(Captains, 1)

    if not captain:
        print("Captain not found")
    else:
        print(f"Captain: {captain.first_name} {captain.last_name}")

        for charter in captain.charters:
            print(f"Charter ID: {charter.id}, title: {charter.title}")