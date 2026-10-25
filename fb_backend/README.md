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

## Booking and availability rules

- Availability depends on the requested date and group size.
- Past dates cannot be booked.
- Group size must be within the trip's minimum and maximum limits.
- Seasonal trips are available only within their season, including both
  boundary dates.
- Trips are unavailable on the captain's days off.
- An active booking blocks the entire charter for the selected date,
  including its other trips.
- Unavailable trips remain in the response with reasons for unavailability.

A new booking has a `PENDING` status and a 15-minute hold.

The total price is calculated when the booking is created:
- `per_person`: trip price multiplied by group size.
- `per_trip`: the trip price, regardless of group size.

The booking stores its price and currency independently of later trip changes.

## Payments

Payment requests require a UUID in the `Idempotency-Key` header.

The mock payment provider supports these tokens:

| Token | Behavior |
| --- | --- |
| `success` | Payment succeeds. |
| `declined` | Payment is declined. |
| `timeout_after_charge` | The provider records a successful payment but returns an error on the first request. |

When a payment succeeds, the booking becomes `CONFIRMED`.

A declined payment allows a new attempt while the booking hold remains valid.
Use a new idempotency key for a new attempt.

If the payment outcome is unknown, the API returns `503` and keeps the
booking and payment in `PROCESSING`. Retry with the same idempotency key
and token to recover the result.

Repeating the same payment request reuses the existing attempt.
Reusing its key with a different booking or token is rejected.

A booking in `PROCESSING` continues to block the charter after its original
hold expires, until the payment outcome is resolved. A successful payment
can therefore confirm the booking after the hold deadline.

## Photos and reviews

Photo files are stored in S3-compatible storage. PostgreSQL stores their
object keys. The API generates signed URLs that expire after 15 minutes.

Reviews are fetched from a mock external provider when a charter has a
linked review business ID.

The `reviews_status` field distinguishes between:
- `available`: reviews were fetched successfully; the list may be empty.
- `unavailable`: the provider could not supply reviews.
- `not_linked`: the charter has no linked review business.

A review provider failure does not prevent the API from returning
the charter details.

## Try the API

Open http://localhost:8002/docs. Expand an endpoint, click **Try it out**,
enter the parameters or request body, and click **Execute**.

### 1. Browse charters and trips

1. Call `GET /charters`.
2. Choose a charter and call `GET /charters/{charter_id}` to see its
   captain, photos, and reviews.
3. Call `GET /charters/{charter_id}/trips`.
4. Call `GET /trips/{trip_id}` to see a single trip.

Demo IDs and seasonal dates are also available in the seed logs:

```bash
docker compose logs seed
```

### 2. Check availability

Call `GET /charters/{charter_id}/trips` with both:
- `date`: a future date, formatted as `YYYY-MM-DD`.
- `group_size`: for example, `4`.

The response from `GET /charters/{charter_id}/trips` includes
`season_start` and `season_end` for each seasonal trip.

Choose a date between these values, including either boundary.
For example, if the response contains:

```json
{
  "season_start": "2026-10-31",
  "season_end": "2026-11-30"
}
```

you can choose `2026-11-02`, provided it is still in the future
and the charter is available.

The demo captain's day off is the day after the seasonal trip's
`season_start`. Its exact date is also printed in the seed logs.

Inspect `available` and `unavailability_reasons` for each trip.

If neither parameter is provided, availability is not evaluated and
`available` is `null`. Providing only one of the two parameters is rejected.

### 3. Create a booking

Call `POST /bookings` with the selected trip ID and an available date:

```json
{
  "trip_id": 1,
  "trip_date": "2030-06-16",
  "group_size": 4,
  "customer": {
    "first_name": "Ana",
    "last_name": "Petrovic",
    "email": "ana@example.com",
    "phone": "+381641234567"
  }
}
```

Replace the example trip ID and date with values appropriate for your data.
The example date can be used with a regular trip while it remains in the future.

The response contains the booking ID, calculated total price,
`PENDING` status, and expiration time.

Call `GET /bookings/{booking_id}` to retrieve the booking.

### 4. Pay for the booking

Before the hold expires, call `POST /bookings/{booking_id}/payments`.

Set the `Idempotency-Key` header to a new UUID. For example:

```text
733027ab-7e11-44ef-955b-11db33727fbe
```

Use this request body:

```json
{
  "token": "success"
}
```

The response should contain a `CONFIRMED` booking and a `SUCCEEDED` payment.

Repeat the request with the same header and body to verify that the same
payment attempt is returned.

Use a fresh UUID for each independent payment attempt.

### 5. Verify that the charter is blocked

Repeat the availability request for the booked date and group size.

Both demo trips belong to the same charter, so both should include
`CHARTER_ALREADY_BOOKED` in their unavailability reasons.