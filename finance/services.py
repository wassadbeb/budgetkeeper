"""Бизнес-логика: категории по умолчанию и вспомогательные функции."""
from decimal import Decimal

from django.db import transaction

from .models import Category

DEFAULT_EXPENSE_CATEGORIES = [
    ("Продукты", "#16a34a"),
    ("Кафе и рестораны", "#f97316"),
    ("Транспорт", "#2563eb"),
    ("Жильё и ЖКХ", "#7c3aed"),
    ("Здоровье", "#dc2626"),
    ("Развлечения", "#db2777"),
    ("Одежда", "#0891b2"),
    ("Связь и интернет", "#65a30d"),
    ("Образование", "#9333ea"),
    ("Прочее", "#64748b"),
]

DEFAULT_INCOME_CATEGORIES = [
    ("Зарплата", "#16a34a"),
    ("Подработка", "#0d9488"),
    ("Подарки", "#f59e0b"),
    ("Проценты и кэшбэк", "#2563eb"),
    ("Прочее", "#64748b"),
]


@transaction.atomic
def create_default_categories(user) -> None:
    """Создаёт стартовый набор категорий для нового пользователя."""
    for name, color in DEFAULT_EXPENSE_CATEGORIES:
        Category.objects.get_or_create(
            user=user,
            name=name,
            kind=Category.Kind.EXPENSE,
            defaults={"color": color, "is_system": True},
        )
    for name, color in DEFAULT_INCOME_CATEGORIES:
        Category.objects.get_or_create(
            user=user,
            name=name,
            kind=Category.Kind.INCOME,
            defaults={"color": color, "is_system": True},
        )


def get_fallback_category(user, kind: str):
    """Возвращает категорию «Прочее» нужного типа или любую подходящую."""
    category = Category.objects.filter(user=user, kind=kind, name="Прочее").first()
    if category:
        return category
    return Category.objects.filter(user=user, kind=kind).first()


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))
