from app.db import SessionLocal
from app.models import Charter, CharterPhoto


object_key = "charters/2/3cde38c5-36d1-4769-9d8a-3aa87e6edf2c.jpg"

with SessionLocal() as session:
    with session.begin():
        charter = session.get(Charter, 2)

        if not charter:
            raise ValueError("Charter not found")

        photo = CharterPhoto(object_key=object_key, charter=charter)
        session.add(photo)
        session.flush()

        print(f"Photo ID: {photo.id}")
        print(f"Photo Object Key: {photo.object_key}")
        print(f"Charter ID: {photo.charter_id}")

    print("Transaction committed.")