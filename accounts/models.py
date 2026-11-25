"""Модели пользователей и токенов восстановления пароля."""
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Учётная запись BudgetKeeper. Вход выполняется по email."""

    class Role(models.TextChoices):
        USER = "user", "Пользователь"
        ADMIN = "admin", "Администратор"

    email = models.EmailField("Email", max_length=150, unique=True)
    full_name = models.CharField("ФИО", max_length=150)
    # В базе колонка называется password_hash: хранится только хеш.
    password = models.CharField("Пароль", max_length=128, db_column="password_hash")
    role = models.CharField(
        "Роль", max_length=20, choices=Role.choices, default=Role.USER
    )
    is_active = models.BooleanField("Активен", default=True)
    is_staff = models.BooleanField("Доступ в админ-панель", default=False)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        db_table = "users"
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["user", "admin"]),
                name="ck_users_role",
            )
        ]

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.full_name.split()[0] if self.full_name else self.email


class PasswordResetToken(models.Model):
    """Одноразовый токен восстановления пароля.

    В базе хранится только SHA-256 хеш токена, поэтому утечка таблицы
    не позволяет воспользоваться ссылками из писем.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="reset_tokens",
        verbose_name="Пользователь",
    )
    token_hash = models.CharField("SHA-256 хеш", max_length=64, unique=True)
    expires_at = models.DateTimeField("Действует до")
    used_at = models.DateTimeField("Использован", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        db_table = "password_reset_token"
        verbose_name = "Токен восстановления пароля"
        verbose_name_plural = "Токены восстановления пароля"
        indexes = [
            models.Index(fields=["user"], name="idx_prt_user_id"),
            models.Index(fields=["expires_at"], name="idx_prt_expires"),
        ]

    def __str__(self) -> str:
        return f"Токен {self.user.email} до {self.expires_at:%d.%m.%Y %H:%M}"

    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()


class Profile(models.Model):
    """Дополнительный профиль пользователя (связь 1:1 с User)."""

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Пользователь",
    )
    phone = models.CharField("Телефон", max_length=20, blank=True)
    birth_date = models.DateField("Дата рождения", null=True, blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        db_table = "profiles"
        verbose_name = "Профиль"
        verbose_name_plural = "Профили"

    def __str__(self) -> str:
        return f"Профиль {self.user.email}"
