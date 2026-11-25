"""Модели предметной области: счета, категории, операции, бюджеты."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Account(models.Model):
    """Счёт пользователя: карта, наличные или банковский счёт."""

    class AccountType(models.TextChoices):
        CASH = "cash", "Наличные"
        CARD = "card", "Карта"
        BANK = "bank", "Банковский счёт"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="accounts",
        verbose_name="Владелец",
    )
    name = models.CharField("Название", max_length=100)
    account_type = models.CharField(
        "Тип счёта",
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.CARD,
    )
    initial_balance = models.DecimalField(
        "Начальный остаток",
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    currency = models.CharField("Валюта", max_length=3, default="RUB")
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        db_table = "accounts"
        verbose_name = "Счёт"
        verbose_name_plural = "Счета"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"], name="uq_accounts_user_name"
            ),
            models.CheckConstraint(
                condition=models.Q(account_type__in=["cash", "card", "bank"]),
                name="ck_accounts_type",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Category(models.Model):
    """Категория доходов или расходов. У каждого пользователя свои."""

    class Kind(models.TextChoices):
        INCOME = "income", "Доход"
        EXPENSE = "expense", "Расход"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
        verbose_name="Владелец",
    )
    name = models.CharField("Название", max_length=80)
    kind = models.CharField(
        "Тип", max_length=10, choices=Kind.choices, default=Kind.EXPENSE
    )
    color = models.CharField("Цвет", max_length=7, default="#4f46e5")
    is_system = models.BooleanField("Системная", default=False)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        db_table = "categories"
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        ordering = ["kind", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "name", "kind"], name="uq_categories_user_name_kind"
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["income", "expense"]),
                name="ck_categories_kind",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class Operation(models.Model):
    """Финансовая операция — главная сущность приложения."""

    class OperationType(models.TextChoices):
        INCOME = "income", "Доход"
        EXPENSE = "expense", "Расход"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="operations",
        verbose_name="Владелец",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="operations",
        verbose_name="Счёт",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="operations",
        verbose_name="Категория",
    )
    operation_type = models.CharField(
        "Тип операции",
        max_length=10,
        choices=OperationType.choices,
        default=OperationType.EXPENSE,
    )
    amount = models.DecimalField(
        "Сумма",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    description = models.TextField("Описание", blank=True)
    occurred_at = models.DateTimeField("Дата операции", default=timezone.now)
    created_by_ai = models.BooleanField("Категория подобрана ИИ", default=False)
    ai_confidence = models.DecimalField(
        "Уверенность ИИ",
        max_digits=4,
        decimal_places=3,
        null=True,
        blank=True,
    )
    is_deleted = models.BooleanField("Удалена", default=False)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        db_table = "operations"
        verbose_name = "Операция"
        verbose_name_plural = "Операции"
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["user", "occurred_at"], name="idx_operations_user_date"),
            models.Index(fields=["category"], name="idx_operations_category"),
            models.Index(fields=["account"], name="idx_operations_account"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="ck_operations_amount_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(operation_type__in=["income", "expense"]),
                name="ck_operations_type",
            ),
            models.CheckConstraint(
                condition=models.Q(ai_confidence__isnull=True)
                | models.Q(ai_confidence__gte=0, ai_confidence__lte=1),
                name="ck_operations_ai_confidence",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_operation_type_display()} {self.amount} ₽ — {self.category}"

    def clean(self) -> None:
        errors = {}
        if self.category_id and self.operation_type:
            if self.category.kind != self.operation_type:
                errors["category"] = "Тип категории не совпадает с типом операции."
        if self.account_id and self.user_id and self.account.user_id != self.user_id:
            errors["account"] = "Счёт принадлежит другому пользователю."
        if self.category_id and self.user_id and self.category.user_id != self.user_id:
            errors["category"] = "Категория принадлежит другому пользователю."
        if errors:
            raise ValidationError(errors)


class Budget(models.Model):
    """Лимит расходов по категории на календарный месяц."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="budgets",
        verbose_name="Владелец",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="budgets",
        verbose_name="Категория",
    )
    period_start = models.DateField("Первый день месяца")
    limit_amount = models.DecimalField(
        "Лимит",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        db_table = "budgets"
        verbose_name = "Бюджет"
        verbose_name_plural = "Бюджеты"
        ordering = ["-period_start", "category__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "category", "period_start"],
                name="uq_budgets_user_category_period",
            ),
            models.CheckConstraint(
                condition=models.Q(limit_amount__gt=0),
                name="ck_budgets_limit_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(period_start__day=1),
                name="ck_budgets_period_first_day",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.category.name}: {self.limit_amount} ₽ на {self.period_start:%m.%Y}"

    def clean(self) -> None:
        if self.category_id and self.category.kind != Category.Kind.EXPENSE:
            raise ValidationError(
                {"category": "Бюджет можно задать только для категории расходов."}
            )


class AISuggestion(models.Model):
    """История подсказок ИИ по категоризации операций."""

    class Source(models.TextChoices):
        RULES = "rules", "Локальные правила"
        LLM = "llm", "Языковая модель"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_suggestions",
        verbose_name="Пользователь",
    )
    operation = models.ForeignKey(
        Operation,
        on_delete=models.SET_NULL,
        related_name="ai_suggestions",
        verbose_name="Операция",
        null=True,
        blank=True,
    )
    input_text = models.TextField("Текст описания")
    suggested_category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="ai_suggestions",
        verbose_name="Предложенная категория",
        null=True,
        blank=True,
    )
    confidence = models.DecimalField(
        "Уверенность", max_digits=4, decimal_places=3, default=Decimal("0.000")
    )
    source = models.CharField(
        "Источник", max_length=10, choices=Source.choices, default=Source.RULES
    )
    accepted = models.BooleanField("Принята пользователем", null=True, blank=True)
    created_at = models.DateTimeField("Создана", auto_now_add=True)

    class Meta:
        db_table = "ai_suggestions"
        verbose_name = "Подсказка ИИ"
        verbose_name_plural = "Подсказки ИИ"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user"], name="idx_ai_suggestions_user")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source__in=["rules", "llm"]),
                name="ck_ai_suggestions_source",
            ),
            models.CheckConstraint(
                condition=models.Q(confidence__gte=0, confidence__lte=1),
                name="ck_ai_suggestions_confidence",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.input_text[:40]} → {self.suggested_category}"
