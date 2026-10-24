from decimal import Decimal
from uuid import uuid4

from app.payment_client import PaymentProviderUnavailable, charge_payment


def charge(key: str, token: str):
    return charge_payment(idempotency_key=key, payment_token=token, amount=Decimal("200.00"), currency="USD")


# 1. Uspešna naplata i ponavljanje iste operacije.
success_key = str(uuid4())

first = charge(success_key, "tok_success")
repeated = charge(success_key, "tok_success")

assert first.status == "SUCCEEDED"
assert repeated == first
print("PASS: Successful charge and identical replay")


# 2. Definitivno odbijena naplata.
declined = charge(str(uuid4()), "tok_declined")
assert declined.status == "DECLINED"
print("PASS: Declined charge")


# 3. Izgubljen odgovor, pa oporavak iste operacije.
recovery_key = str(uuid4())

try:
    charge(recovery_key, "tok_timeout_after_charge")
except PaymentProviderUnavailable:
    print("PASS: Lost response reported as unknown outcome")
else:
    raise AssertionError("Expected an unknown payment outcome.")

recovered = charge(recovery_key,"tok_timeout_after_charge")
assert recovered.status == "SUCCEEDED"

repeated_recovery = charge(recovery_key,"tok_timeout_after_charge")
assert repeated_recovery == recovered
print("PASS: Charge recovered without creating a new payment")