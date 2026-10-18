from decimal import Decimal, ROUND_HALF_UP


def underbilling(quantity, agreed_price, invoiced_price):
    """USD, invoice quantity, net prices after authorized discounts, before tax."""
    q, agreed, billed = map(lambda x: Decimal(str(x)), (quantity, agreed_price, invoiced_price))
    if q <= 0 or min(agreed, billed) < 0:
        raise ValueError("Quantity must be positive; prices cannot be negative.")
    return (q * max(agreed - billed, Decimal("0"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
