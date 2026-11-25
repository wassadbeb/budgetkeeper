"""Представления регистрации, входа и восстановления пароля."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from finance.services import create_default_categories

from .forms import (
    LoginForm,
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    RegisterForm,
)
from .models import User
from .services import consume_token, create_reset_token, get_valid_token


def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("finance:dashboard")

    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        create_default_categories(user)
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Аккаунт создан. Добро пожаловать в BudgetKeeper!")
        return redirect("finance:dashboard")

    return render(request, "accounts/register.html", {"form": form})


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = "accounts:login"


def password_reset_request(request: HttpRequest) -> HttpResponse:
    form = PasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            raw_token = create_reset_token(user)
            reset_url = request.build_absolute_uri(
                reverse("accounts:password_reset_confirm", args=[raw_token])
            )
            send_mail(
                subject="Восстановление пароля BudgetKeeper",
                message=(
                    "Здравствуйте!\n\n"
                    "Вы запросили восстановление пароля. Ссылка действует "
                    "30 минут и может быть использована один раз:\n\n"
                    f"{reset_url}\n\n"
                    "Если вы не запрашивали восстановление, просто проигнорируйте письмо."
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )
        # Одинаковый ответ для существующего и несуществующего адреса.
        messages.success(
            request,
            "Если адрес зарегистрирован, письмо со ссылкой для сброса пароля отправлено.",
        )
        return redirect("accounts:password_reset")

    return render(request, "accounts/password_reset.html", {"form": form})


def password_reset_confirm(request: HttpRequest, token: str) -> HttpResponse:
    reset_token = get_valid_token(token)
    if reset_token is None:
        return render(
            request,
            "accounts/password_reset_invalid.html",
            status=400,
        )

    form = PasswordResetConfirmForm(reset_token.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        consume_token(reset_token)
        messages.success(request, "Пароль изменён. Войдите с новым паролем.")
        return redirect("accounts:login")

    return render(
        request,
        "accounts/password_reset_confirm.html",
        {"form": form},
    )
