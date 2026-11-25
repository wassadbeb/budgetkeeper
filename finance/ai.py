"""ИИ-сервис BudgetKeeper.

Если задан OPENAI_API_KEY, категория подбирается языковой моделью.
Без ключа (и при любой ошибке внешнего API) используется локальный
эвристический классификатор по ключевым словам. Приложение остаётся
работоспособным полностью офлайн.
"""
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings

from .models import Category

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Продукты": [
        "продукт",
        "супермаркет",
        "магазин",
        "пятёрочка",
        "пятерочка",
        "магнит",
        "перекрёсток",
        "перекресток",
        "ашан",
        "лента",
        "вкусвилл",
        "дикси",
        "еда домой",
    ],
    "Кафе и рестораны": [
        "кафе",
        "ресторан",
        "кофе",
        "кофейня",
        "бар",
        "пицца",
        "суши",
        "доставка еды",
        "вкусно и точка",
        "столовая",
        "обед",
    ],
    "Транспорт": [
        "метро",
        "автобус",
        "трамвай",
        "такси",
        "бензин",
        "заправка",
        "азс",
        "каршеринг",
        "парковка",
        "электричка",
        "проездной",
    ],
    "Жильё и ЖКХ": [
        "аренда",
        "квартира",
        "жкх",
        "коммуналка",
        "электричество",
        "вода",
        "отопление",
        "управляющая компания",
        "ипотека",
    ],
    "Здоровье": [
        "аптека",
        "врач",
        "клиника",
        "больница",
        "анализы",
        "стоматолог",
        "лекарство",
        "витамины",
    ],
    "Развлечения": [
        "кино",
        "театр",
        "концерт",
        "игра",
        "steam",
        "подписка",
        "нетфликс",
        "боулинг",
        "музей",
    ],
    "Одежда": [
        "одежда",
        "обувь",
        "куртка",
        "джинсы",
        "кроссовки",
        "футболка",
        "платье",
        "wildberries",
        "ozon",
    ],
    "Связь и интернет": [
        "связь",
        "интернет",
        "мтс",
        "билайн",
        "мегафон",
        "теле2",
        "телефон",
        "домашний интернет",
    ],
    "Образование": [
        "курс",
        "книга",
        "обучение",
        "университет",
        "колледж",
        "лекция",
        "учебник",
        "skillbox",
        "stepik",
    ],
    "Зарплата": ["зарплата", "аванс", "премия", "оклад", "выплата"],
    "Подработка": ["фриланс", "подработка", "заказ", "гонорар", "проект"],
    "Подарки": ["подарок", "подарили", "день рождения"],
    "Проценты и кэшбэк": ["кэшбэк", "кешбэк", "проценты", "вклад", "дивиденды"],
}


@dataclass
class Suggestion:
    category: Category | None
    confidence: float
    source: str
    reason: str = ""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower().replace("ё", "е")).strip()


def _suggest_with_rules(
    description: str, categories: list[Category], operation_type: str
) -> Suggestion:
    text = _normalize(description)
    best_category = None
    best_hits = 0
    best_keyword = ""

    for category in categories:
        keywords = CATEGORY_KEYWORDS.get(category.name, [])
        hits = sum(1 for keyword in keywords if _normalize(keyword) in text)
        if hits > best_hits:
            best_category = category
            best_hits = hits
            best_keyword = next(
                (kw for kw in keywords if _normalize(kw) in text), ""
            )

    if best_category is None:
        fallback = next((c for c in categories if c.name == "Прочее"), None)
        return Suggestion(
            category=fallback or (categories[0] if categories else None),
            confidence=0.30,
            source="rules",
            reason="Ключевые слова не найдены, выбрана категория «Прочее».",
        )

    confidence = min(0.95, 0.60 + 0.15 * best_hits)
    return Suggestion(
        category=best_category,
        confidence=round(confidence, 3),
        source="rules",
        reason=f"Найдено ключевое слово «{best_keyword}».",
    )


def _suggest_with_llm(
    description: str, categories: list[Category], operation_type: str
) -> Suggestion | None:
    api_key = (settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")).strip()
    if not api_key:
        return None

    names = [category.name for category in categories]
    kind_label = "расхода" if operation_type == Category.Kind.EXPENSE else "дохода"
    prompt = (
        "Ты — модуль категоризации личных финансов. "
        f"Определи наиболее подходящую категорию {kind_label} из списка: "
        f"{', '.join(names)}. "
        "Верни строго JSON без пояснений: "
        '{"category": "<название из списка>", "confidence": <число от 0 до 1>, '
        '"reason": "<краткое обоснование>"}.'
    )
    body = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": description[:1000]},
        ],
        "response_format": {"type": "json_object"},
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
        with urllib.request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        category_name = str(parsed.get("category", "")).strip().lower()
        category = next(
            (c for c in categories if c.name.lower() == category_name), None
        )
        if category is None:
            return None
        confidence = float(parsed.get("confidence", 0.8))
        return Suggestion(
            category=category,
            confidence=min(1.0, max(0.0, confidence)),
            source="llm",
            reason=str(parsed.get("reason", ""))[:200],
        )
    except (urllib.error.URLError, KeyError, ValueError, TypeError, TimeoutError):
        return None


def suggest_category(description: str, user, operation_type: str) -> Suggestion:
    """Подбирает категорию по тексту описания операции."""
    categories = list(
        Category.objects.filter(user=user, kind=operation_type).order_by("name")
    )
    if not categories:
        return Suggestion(None, 0.0, "rules", "У пользователя нет категорий.")

    llm_result = _suggest_with_llm(description, categories, operation_type)
    if llm_result is not None:
        return llm_result
    return _suggest_with_rules(description, categories, operation_type)


def build_budget_advice(
    income, expense, budget_rows: list[dict], category_rows: list[dict]
) -> list[str]:
    """Формирует короткие советы по бюджету на основе фактических данных."""
    advice: list[str] = []
    income = float(income or 0)
    expense = float(expense or 0)

    if income > 0:
        savings_rate = (income - expense) / income * 100
        if savings_rate < 0:
            advice.append(
                "Расходы превышают доходы. Стоит пересмотреть необязательные траты "
                "и установить лимиты по категориям."
            )
        elif savings_rate < 10:
            advice.append(
                "На сбережения уходит менее 10% дохода. Попробуйте правило "
                "50/30/20: 20% дохода направлять в накопления."
            )
        else:
            advice.append(
                f"Вы сохраняете около {savings_rate:.0f}% дохода — хороший темп. "
                "Можно оформить накопительный счёт под проценты."
            )
    else:
        advice.append(
            "За выбранный месяц доходы не зафиксированы. Добавьте поступления, "
            "чтобы оценка бюджета была точной."
        )

    over_budget = [row for row in budget_rows if row["over"]]
    if over_budget:
        names = ", ".join(row["budget"].category.name for row in over_budget[:3])
        advice.append(f"Превышен лимит по категориям: {names}. Сократите траты.")
    else:
        near_limit = [
            row for row in budget_rows if 80 <= row["percent"] < 100
        ]
        if near_limit:
            names = ", ".join(row["budget"].category.name for row in near_limit[:3])
            advice.append(f"Близко к лимиту: {names}. Осталось менее 20% бюджета.")

    if category_rows:
        top = category_rows[0]
        if expense > 0 and top["percent"] >= 40:
            advice.append(
                f"Крупнейшая статья расходов — «{top['name']}» "
                f"({top['percent']}% всех трат). Проверьте, нет ли лишних покупок."
            )

    if len(advice) == 1:
        advice.append(
            "Бюджет сбалансирован. Продолжайте фиксировать операции — "
            "так рекомендации будут точнее."
        )
    return advice[:3]
