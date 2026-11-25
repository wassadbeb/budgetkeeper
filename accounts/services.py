"""Сервисные функции механизма восстановления пароля."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import PasswordResetToken


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_reset_token(user) -> str:
    """Создаёт токен, сохраняет его хеш и возвращает сырое значение.

    Сырой токен попадает только в письмо и не сохраняется в базе.
    """
    raw_token = secrets.token_urlsafe(32)
    PasswordResetToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )
    PasswordResetToken.objects.create(
        user=user,
        token_hash=_hash_token(raw_token),
        expires_at=timezone.now()
        + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT),
    )
    return raw_token


def get_valid_token(raw_token: str) -> PasswordResetToken | None:
    if not raw_token:
        return None
    token = (
        PasswordResetToken.objects.select_related("user")
        .filter(token_hash=_hash_token(raw_token))
        .first()
    )
    if token and token.is_valid():
        return token
    return None


def consume_token(token: PasswordResetToken) -> None:
    """Помечает токен использованным: повторная ссылка не сработает."""
    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])
