"""Админ-панель финансового модуля."""
from django.contrib import admin

from .models import AIMessage, AISuggestion, Account, Budget, Category, Operation


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "account_type", "initial_balance", "is_active")
    list_filter = ("account_type", "is_active")
    search_fields = ("name", "user__email")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "kind", "is_system")
    list_filter = ("kind", "is_system")
    search_fields = ("name", "user__email")


@admin.register(Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "user",
        "operation_type",
        "amount",
        "category",
        "account",
        "created_by_ai",
    )
    list_filter = ("operation_type", "created_by_ai", "is_deleted")
    search_fields = ("description", "user__email")
    autocomplete_fields = ("category", "account")
    date_hierarchy = "occurred_at"


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "period_start", "limit_amount")
    list_filter = ("period_start",)
    search_fields = ("user__email", "category__name")


@admin.register(AISuggestion)
class AISuggestionAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "input_text",
        "suggested_category",
        "confidence",
        "source",
        "accepted",
    )
    list_filter = ("source", "accepted")
    search_fields = ("input_text", "user__email")
    readonly_fields = ("created_at",)


@admin.register(AIMessage)
class AIMessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "role", "content")
    list_filter = ("role",)
    search_fields = ("content", "user__email")
    readonly_fields = ("created_at",)
