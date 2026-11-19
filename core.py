"""Pure parsing, scoring and ordering for Live Cast — no network dependencies."""
from __future__ import annotations
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

HASHTAG_RE = re.compile(r'(?<!\w)#([\w]+)', flags=re.UNICODE)


def normalized_tag(value: str) -> str:
    return value.strip().lstrip('#').casefold()


def matched_cast_ids(message: str, cast: list[dict]) -> list[str]:
    tags = {normalized_tag(match.group(1)) for match in HASHTAG_RE.finditer(message or '')}
    matches = [m['id'] for m in cast if m.get('active', True) and tags.intersection(
        normalized_tag(tag) for tag in m['hashtags'])]
    return matches


def validate_aliases(cast: list[dict]) -> None:
    ids, tags = set(), {}
    for member in cast:
        if member['id'] in ids:
            raise ValueError('Duplicate cast ID')
        ids.add(member['id'])
        if not member['name'].strip():
            raise ValueError('Cast names cannot be empty')
        for original in member['hashtags']:
            tag = normalized_tag(original)
            if not tag or not re.fullmatch(r'\w+', tag, flags=re.UNICODE):
                raise ValueError(f'Invalid hashtag: {original}; use a single word')
            if tag in tags and tags[tag] != member['id']:
                raise ValueError(f'Hashtag #{tag} already belongs to another cast member')
            tags[tag] = member['id']


def parse_amount_to_micros(value: str | int | float | Decimal) -> int:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('Invalid dollar amount')
    if not amount.is_finite() or amount <= 0 or amount > 100_000:
        raise ValueError('Amount must be between $0.01 and $100,000')
    if amount.as_tuple().exponent < -2:
        raise ValueError('Use no more than 2 decimal places')
    return int((amount * 1_000_000).to_integral_value(rounding=ROUND_HALF_UP))


def points_milli(amount_micros: int, multiplier: str, currency: str = 'USD') -> int:
    if currency.upper() != 'USD':
        return 0
    points = (Decimal(amount_micros) / Decimal(1_000_000)) * Decimal(multiplier)
    return int((points * 1000).to_integral_value(rounding=ROUND_HALF_UP))


def format_points(value: int) -> str:
    return format(Decimal(value) / Decimal(1000), '.2f')


def rank_members(cast: list[dict], score_map: dict[str, int]) -> list[dict]:
    active = [m for m in cast if m['active']]
    ordered = sorted(active, key=lambda m: (-score_map.get(m['id'], 0), m['name'].casefold(), m['id']))
    return [dict(id=m['id'], name=m['name'], hashtags=m['hashtags'], rank=i+1,
                 points=format_points(score_map.get(m['id'], 0)), points_milli=score_map.get(m['id'], 0))
            for i, m in enumerate(ordered)]


def classify_event(event: dict, cast: list[dict], multiplier: str) -> dict | None:
    """Accepts the shape of YouTube liveChatMessages.list().items[] (or synthetic equivalent)."""
    snippet = event.get('snippet') or {}
    kind = snippet.get('type')
    if kind not in ('superChatEvent', 'superStickerEvent'):
        return None  # Ordinary chat must never change the money scoreboard.
    details = snippet.get('superChatDetails' if kind == 'superChatEvent' else 'superStickerDetails') or {}
    if 'amountMicros' not in details or not event.get('id'):
        raise ValueError('Missing paid-event id or amountMicros')
    amount_micros = int(details['amountMicros'])
    if amount_micros <= 0:
        raise ValueError('Paid-event amount must be positive')
    currency = str(details.get('currency', '')).upper()
    message = str(details.get('userComment', '') if kind == 'superChatEvent' else '')
    matched = matched_cast_ids(message, cast)
    status = 'review_currency' if currency != 'USD' else ('assigned' if len(matched) == 1 else 'review')
    cast_id = matched[0] if len(matched) == 1 else None
    return {
        'id': str(event['id']), 'kind': kind,
        'donor': str((event.get('authorDetails') or {}).get('displayName', 'Viewer'))[:120],
        'message': message[:500], 'amount_micros': amount_micros,
        'currency': currency, 'amount_display': str(details.get('amountDisplayString', ''))[:80],
        'cast_id': cast_id, 'status': status,
        'points_milli': points_milli(amount_micros, multiplier, currency),
        'published_at': str(snippet.get('publishedAt', ''))[:80],
    }
