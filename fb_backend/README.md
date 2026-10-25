# Fishing Charter Booking API

A backend API for browsing fishing charters and trips, checking availability,
creating bookings, and processing payments.

## Technology stack

- Python 3.11 and FastAPI
- SQLAlchemy and PostgreSQL
- Alembic migrations
- S3-compatible photo storage, provided locally by Moto
- Mock payment and review providers
- Docker Compose
- unittest

## Requirements

- Docker with Docker Compose
- Git

Python does not need to be installed on the host machine.

## Run the application

From the project root, run:

```bash
docker compose up --build -d
```

Startup automatically applies database migrations and seeds demo data,
including a charter, two trips, a captain's day off, and a photo.

The seed can be run repeatedly without duplicating demo records.

### Service URLs

| Service | URL |
| --- | --- |
| API documentation | http://localhost:8002/docs |
| API health check | http://localhost:8002/health |
| OpenAPI schema | http://localhost:8002/openapi.json |
| Mock payment provider documentation | http://localhost:8003/docs |
| Mock review provider documentation | http://localhost:8004/docs |

### View startup status and demo data

```bash
docker compose ps -a
docker compose logs migrate seed
```

The `migrate` and `seed` services should finish with exit code `0`.
These services perform startup tasks and do not run continuously.

Seed logs show the generated demo IDs, season dates, and captain's day off.
Use those values when exploring the API.

### Stop the application

```bash
docker compose down
```

This preserves the PostgreSQL and mock payment provider data stored in
Docker volumes. Demo photos are uploaded to local S3 storage during startup.

## Run automated tests

```bash
docker compose --profile test run --build --rm tests
```

Tests use unittest and a separate PostgreSQL service named `test-db`,
with a database named `booking_test`. They do not use the application database.

The test setup applies Alembic migrations automatically and clears test
records between tests.