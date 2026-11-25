"""ИИ-агент BudgetKeeper: финансовый ассистент с контекстом из базы данных.

Агент отличается от простого чата тем, что получает роль (системный
промпт), актуальный контекст о доходах/расходах пользователя из БД и
историю диалога. Без ключа (или при недоступности провайдера) отвечает
локальной заглушкой, поэтому приложение остаётся работоспособным офлайн.
Поддерживаются любые OpenAI-совместимые провайдеры: OpenAI, OpenRouter,
локальный Ollama (OPENAI_BASE_URL=http://localhost:11434/v1).
"""
import json
import os
import urllib.error
import urllib.request

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .models import Operation

SYSTEM_PROMPT = (
    "Ты — финансовый ассистент BudgetKeeper. Твоя роль — помогать пользователю "
    "анализировать личные расходы и давать конкретные, выполнимые советы по "
    "бюджету. Отвечай кратко и по-русски, опираясь только на предоставленный "
    "контекст о доходах и расходах пользователя."
)


def _build_user_context(user) -> str:
    """Собирает сводку по бюджету текущего месяца для системного промпта."""
    today = timezone.localdate()
    start = today.replace(day=1)
    month = Operation.objects.filter(
        user=user, is_deleted=False, occurred_at__date__gte=start
    )
    income = (
        month.filter(operation_type=Operation.OperationType.INCOME).aggregate(
            s=Sum("amount")
        )["s"]
        or 0
    )
    expense = (
        month.filter(operation_type=Operation.OperationType.EXPENSE).aggregate(
            s=Sum("amount")
        )["s"]
        or 0
    )
    top = (
        month.filter(operation_type=Operation.OperationType.EXPENSE)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")[:3]
    )
    top_text = "; ".join(f"{row['category__name']} — {row['total']} ₽" for row in top)
    return (
        f"Текущий месяц: доходы {income} ₽, расходы {expense} ₽. "
        f"Крупнейшие статьи расходов: {top_text}."
    )


def _ask_llm(system: str, history: list[dict], user_text: str) -> str | None:
    """Обращение к OpenAI-совместимому провайдеру; None при ошибке/отсутствии ключа."""
    api_key = (settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return None

    messages = [{"role": "system", "content": system}]
    for message in history[-6:]:
        messages.append({"role": message["role"], "content": message["content"]})
    messages.append({"role": "user", "content": user_text})

    body = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.4,
        "messages": messages,
    }
    request = urllib.request.Request(
        f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, ValueError, TypeError, TimeoutError):
        return None


def _ask_local(user_text: str, context: str) -> str:
    """Офлайн-ответ на основе контекста (без внешнего API)."""
    return (
        "Работаю в офлайн-режиме, поэтому отвечаю по локальным данным. "
        + context
        + " Рекомендую зафиксировать все траты и установить лимиты по крупным "
        "категориям расходов."
    )


def ask_agent(user, user_text: str, history: list[dict]) -> str:
    """Возвращает ответ ассистента на сообщение пользователя."""
    context = _build_user_context(user)
    system = SYSTEM_PROMPT + "\n\nКонтекст пользователя:\n" + context
    answer = _ask_llm(system, history, user_text)
    if answer is None:
        answer = _ask_local(user_text, context)
    return answer
