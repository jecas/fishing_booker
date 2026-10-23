from sqlalchemy import select

from app.db import SessionLocal
from app.models import Captains


with SessionLocal() as session:
    statement = select(Captains).order_by(Captains.id)

    captains = session.scalars(statement).all()

    for captain in captains:
        print(captain.id, captain.first_name, captain.last_name, captain.email, captain.phone)