"""Маршруты REST API (префикс /api/)."""
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.api import (
    PasswordResetConfirmAPIView,
    PasswordResetRequestAPIView,
    RegisterAPIView,
)

from .api import OperationDetailView, OperationListCreateView, StatsAPIView

app_name = "api"

urlpatterns = [
    # Аутентификация
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/login/", TokenObtainPairView.as_view(), name="login"),
    path(
        "auth/password-reset/request/",
        PasswordResetRequestAPIView.as_view(),
        name="password_reset_request",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmAPIView.as_view(),
        name="password_reset_confirm",
    ),
    # Операции (полный CRUD)
    path("operations/", OperationListCreateView.as_view(), name="operation_list_create"),
    path("operations/<int:pk>/", OperationDetailView.as_view(), name="operation_detail"),
    # Статистика (только администратор)
    path("stats/", StatsAPIView.as_view(), name="stats"),
]
