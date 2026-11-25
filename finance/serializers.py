"""Сериализаторы REST API финансового модуля."""
from rest_framework import serializers

from .models import Operation


class OperationSerializer(serializers.ModelSerializer):
    """Сериализатор финансовой операции с серверной валидацией."""

    class Meta:
        model = Operation
        fields = [
            "id",
            "operation_type",
            "amount",
            "account",
            "category",
            "description",
            "occurred_at",
            "created_by_ai",
            "ai_confidence",
        ]
        read_only_fields = ["created_by_ai", "ai_confidence"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Сумма операции должна быть положительной.")
        return value

    def validate(self, attrs):
        """Проверяет согласованность типа операции, категории и счёта."""
        user = self.context["request"].user
        operation_type = attrs.get("operation_type", getattr(self.instance, "operation_type", None))
        category = attrs.get("category", getattr(self.instance, "category", None))
        account = attrs.get("account", getattr(self.instance, "account", None))

        if category and operation_type and category.kind != operation_type:
            raise serializers.ValidationError(
                {"category": "Тип категории не совпадает с типом операции."}
            )
        if account and account.user_id != user.id:
            raise serializers.ValidationError(
                {"account": "Счёт принадлежит другому пользователю."}
            )
        if category and category.user_id != user.id:
            raise serializers.ValidationError(
                {"category": "Категория принадлежит другому пользователю."}
            )
        return attrs
