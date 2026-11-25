"""Декораторы разграничения прав доступа по ролям (RBAC)."""
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect


def role_required(allowed_roles):
    """Пропускает только аутентифицированных пользователей с нужной ролью.

    Неавторизованный пользователь перенаправляется на страницу входа,
    пользователь с неподходящей ролью получает ошибку 403 Forbidden
    (HTML-страница 403.html).
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if request.user.role not in allowed_roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def api_role_required(allowed_roles):
    """То же, что role_required, но для JSON-эндпоинтов.

    Возвращает структурированный JSON-ответ с кодом 401/403 вместо
    HTML-страницы, чтобы фронтенд мог корректно обработать ошибку.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Unauthorized"}, status=401)
            if request.user.role not in allowed_roles:
                return JsonResponse(
                    {
                        "error": "Forbidden",
                        "message": "Требуются права администратора.",
                    },
                    status=403,
                )
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
