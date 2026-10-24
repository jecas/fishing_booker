import os
import sqlite3
from uuid import uuid4
from contextlib import closing
from datetime import datetime, timezone


def get_connection():
    connection = sqlite3.connect(os.environ.get("PAYMENT_DB_PATH", "/data/payments.sqlite3"), timeout=10)
    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    with closing(get_connection()) as connection:
        with connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS charges (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    request_hash TEXT NOT NULL,
                    status TEXT NOT NULL
                        CHECK (status IN ('SUCCEEDED', 'DECLINED')),
                    created_at TEXT NOT NULL
                )
                """
            )


def get_or_create_charge(idempotency_key, request_hash, status) -> tuple[dict, bool]:
    with closing(get_connection()) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")

            existing = connection.execute(
                """
                SELECT id, idempotency_key, request_hash, status, created_at
                FROM charges
                WHERE idempotency_key = ?
                """,
                (idempotency_key,)
            ).fetchone()
            if existing:
                if existing['request_hash'] != request_hash:
                    raise ValueError("Idempotency key was used with a different request.")

                return dict(existing), False

            charge = {
                "id": str(uuid4()),
                "idempotency_key": idempotency_key,
                "request_hash": request_hash,
                "status": status,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            connection.execute(
                """
                INSERT INTO charges (id, idempotency_key, request_hash, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (charge["id"], charge["idempotency_key"], charge["request_hash"], charge["status"],
                 charge["created_at"])
            )

            return charge, True