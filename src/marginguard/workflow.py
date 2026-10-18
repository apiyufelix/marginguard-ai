"""Pure investigation policy. All financial inputs remain exact Decimal values."""
from decimal import Decimal
import re

ALLOWED_TRANSITIONS = {
    'open': ('investigating', 'dismissed'),
    'investigating': ('confirmed', 'dismissed'),
    'confirmed': ('resolved', 'investigating'),
    'dismissed': ('investigating',),
    'resolved': ('confirmed',),
}

class CasePolicyError(ValueError):
    pass


def required_text(value, label, maximum=2000):
    value = str(value).strip() if value is not None else ''
    if not value:
        raise CasePolicyError(f'{label} is required.')
    if len(value) > maximum or '\x00' in value:
        raise CasePolicyError(f'{label} must be at most {maximum} characters and contain no null characters.')
    return value


def money(value):
    value = str(value).strip()
    if not re.fullmatch(r'[0-9]{1,22}(\.[0-9]{1,2})?', value):
        raise CasePolicyError('Use a nonnegative USD amount with at most two decimal places, without currency symbols or separators.')
    return Decimal(value).quantize(Decimal('0.01'))


def transition_amount(current, target, potential, confirmed, net_recovered,
                      confirmation=None, close_with_balance=False):
    if target not in ALLOWED_TRANSITIONS.get(current, ()):
        raise CasePolicyError('That status change is not allowed from the current status.')
    if current == 'investigating' and target == 'confirmed':
        amount = money(confirmation)
        if not Decimal('0') < amount <= potential:
            raise CasePolicyError('Confirmed amount must be positive and cannot exceed potential underbilling.')
        return amount
    if current == 'confirmed' and target == 'investigating':
        if net_recovered != 0:
            raise CasePolicyError('Reverse recorded recoveries before withdrawing confirmation.')
        return None
    if current == 'confirmed' and target == 'resolved':
        if confirmed > net_recovered and not close_with_balance:
            raise CasePolicyError('An unrecovered balance remains. Explicitly choose to close with that balance or keep investigating the recovery.')
        return confirmed
    if current == 'resolved' and target == 'confirmed':
        return confirmed
    return None


def validate_recovery(status, confirmed, net_recovered, amount):
    amount = money(amount)
    if status != 'confirmed':
        raise CasePolicyError('Recoveries can be recorded only on confirmed cases. Reopen a resolved case first.')
    if amount <= 0:
        raise CasePolicyError('Recovery amount must be positive.')
    if amount > confirmed - net_recovered:
        raise CasePolicyError('Recovery exceeds the remaining confirmed balance.')
    return amount
