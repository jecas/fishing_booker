from sqlalchemy import text

from app.db import engine

with engine.connect() as conn:
    result = conn.execute(text("SELECT current_database(), version()"))
    print(result.one())