"""API-представления аутентификации: регистрация и восстановление пароля."""
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from finance.services import create_default_categories

from .models import Profile, User
from .services import consume_token, create_reset_token, get_valid_token


class RegisterSerializer(serializers.Serializer):
    """Сериализатор регистрации с валидацией сложности пароля."""

    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        return value

    def validate_password(self, value):
        candidate = User(email=self.initial_data.get("email", ""))
        try:
            validate_password(value, candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            role=User.Role.USER,
        )
        Profile.objects.get_or_create(user=user)
        create_default_categories(user)
        return user


class RegisterAPIView(APIView):
    """POST /api/auth/register/ — регистрация пользователя."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "message": "Регистрация успешна.",
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class PasswordResetRequestAPIView(APIView):
    """POST /api/auth/password-reset/request/ — запрос сброса пароля."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            create_reset_token(user)
            # Письмо отправляется через send_mail; на учебном стенде — в консоль.
        return Response(
            {
                "message": "Если адрес зарегистрирован, ссылка для сброса отправлена.",
            },
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmAPIView(APIView):
    """POST /api/auth/password-reset/confirm/ — установка нового пароля."""

    permission_classes = [AllowAny]

    def post(self, request):
        raw_token = (request.data.get("token") or "").strip()
        new_password = request.data.get("password") or ""
        reset_token = get_valid_token(raw_token)
        if reset_token is None:
            return Response(
                {"error": "Ссылка недействительна или устарела."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = reset_token.user
        try:
            validate_password(new_password, user)
        except DjangoValidationError as exc:
            return Response(
                {"password": list(exc.messages)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        user.set_password(new_password)
        user.save(update_fields=["password_hash"])
        consume_token(reset_token)
        return Response(
            {"message": "Пароль успешно изменён."},
            status=status.HTTP_200_OK,
        )
