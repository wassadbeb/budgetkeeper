"""Формы финансового модуля."""
from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Account, Budget, Category, Operation


class OperationForm(forms.ModelForm):
    occurred_at = forms.DateTimeField(
        label="Дата и время",
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "input"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=["%Y-%m-%dT%H:%M"],
        initial=timezone.now,
    )

    class Meta:
        model = Operation
        fields = (
            "operation_type",
            "amount",
            "account",
            "category",
            "description",
            "occurred_at",
        )
        widgets = {
            "operation_type": forms.Select(attrs={"class": "input"}),
            "amount": forms.NumberInput(
                attrs={"class": "input", "step": "0.01", "min": "0.01"}
            ),
            "account": forms.Select(attrs={"class": "input"}),
            "category": forms.Select(attrs={"class": "input"}),
            "description": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "Например: продукты в Пятёрочке на неделю",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(
            user=user, is_active=True
        )
        self.fields["category"].queryset = Category.objects.filter(user=user)
        self.fields["category"].required = False
        self.fields["category"].empty_label = "Подобрать автоматически по описанию"
        if user and not self.instance.pk:
            self.fields["account"].initial = (
                Account.objects.filter(user=user, is_active=True).first()
            )

    def clean(self):
        cleaned = super().clean()
        operation_type = cleaned.get("operation_type")
        category = cleaned.get("category")
        if category and operation_type and category.kind != operation_type:
            self.add_error(
                "category",
                "Выберите категорию, соответствующую типу операции "
                f"«{dict(Operation.OperationType.choices).get(operation_type)}».",
            )
        return cleaned


class BudgetForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        label="Категория расходов",
        widget=forms.Select(attrs={"class": "input"}),
    )
    period = forms.CharField(
        label="Месяц",
        widget=forms.DateInput(attrs={"type": "month", "class": "input"}),
    )
    limit_amount = forms.DecimalField(
        label="Лимит, ₽",
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(
            attrs={"class": "input", "step": "0.01", "min": "0.01"}
        ),
    )

    def __init__(self, *args, user=None, initial_period: date | None = None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            user=user, kind=Category.Kind.EXPENSE
        )
        if initial_period and not self.is_bound:
            self.fields["period"].initial = initial_period.strftime("%Y-%m")

    def clean_period(self) -> date:
        value = self.cleaned_data["period"]
        try:
            year, month = (int(part) for part in value.split("-")[:2])
            return date(year, month, 1)
        except (ValueError, TypeError):
            raise ValidationError("Укажите месяц в формате ГГГГ-ММ.")

    def save(self) -> Budget:
        budget, _ = Budget.objects.update_or_create(
            user=self.user,
            category=self.cleaned_data["category"],
            period_start=self.cleaned_data["period"],
            defaults={"limit_amount": self.cleaned_data["limit_amount"]},
        )
        return budget


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "kind", "color")
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input", "placeholder": "Например, Спорт"}
            ),
            "kind": forms.Select(attrs={"class": "input"}),
            "color": forms.TextInput(attrs={"type": "color", "class": "input color"}),
        }


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ("name", "account_type", "initial_balance")
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "input", "placeholder": "Например, Карта Сбербанка"}
            ),
            "account_type": forms.Select(attrs={"class": "input"}),
            "initial_balance": forms.NumberInput(
                attrs={"class": "input", "step": "0.01"}
            ),
        }
