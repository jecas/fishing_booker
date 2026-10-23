from app.db import SessionLocal
from app.models import Captains, Charter


with SessionLocal() as session:
    with session.begin():
        captain = session.get(Captains, 1)

        if not captain:
            raise ValueError("Captain not found")

        charter = Charter(title="Petar's boat", description="Private boat trips.", captain=captain)
        session.add(charter)
        session.flush()

        print(f"Charter ID: {charter.id}")
        print(f"Charter Caption ID: {charter.captain_id}")
        print(f"Charter Caption: {charter.captain.first_name} {charter.captain.last_name}")

    print("Transaction committed.")