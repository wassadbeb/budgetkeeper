"""Представления BudgetKeeper: дашборд, операции, бюджеты, справочники, API."""
import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .agent import ask_agent
from .ai import build_budget_advice, suggest_category
from .forms import AccountForm, BudgetForm, CategoryForm, OperationForm
from .models import AIMessage, AISuggestion, Account, Budget, Category, Operation
from .services import get_fallback_category

MONTHS_RU = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
]


def _parse_month(value: str | None) -> date:
    today = timezone.localdate()
    if value:
        try:
            year, month = (int(part) for part in value.split("-")[:2])
            return date(year, month, 1)
        except (ValueError, TypeError):
            pass
    return today.replace(day=1)


def _month_context(period: date) -> dict:
    next_month = (period.replace(day=28) + timedelta(days=4)).replace(day=1)
    previous_month = (period - timedelta(days=1)).replace(day=1)
    return {
        "period": period,
        "month_value": period.strftime("%Y-%m"),
        "month_label": f"{MONTHS_RU[period.month - 1]} {period.year}",
        "prev_month": previous_month.strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m"),
        "next_month_date": next_month,
    }


def _month_bounds(period: date):
    tz = timezone.get_current_timezone()
    next_month = (period.replace(day=28) + timedelta(days=4)).replace(day=1)
    start = timezone.make_aware(datetime.combine(period, time.min), tz)
    end = timezone.make_aware(datetime.combine(next_month, time.min), tz)
    return start, end


@login_required
def dashboard(request):
    period = _parse_month(request.GET.get("month"))
    context = _month_context(period)
    start, end = _month_bounds(period)

    base = Operation.objects.filter(user=request.user, is_deleted=False)
    month_ops = base.filter(occurred_at__gte=start, occurred_at__lt=end)

    totals = month_ops.aggregate(
        income=Sum("amount", filter=Q(operation_type=Operation.OperationType.INCOME)),
        expense=Sum(
            "amount", filter=Q(operation_type=Operation.OperationType.EXPENSE)
        ),
    )
    income = totals["income"] or Decimal("0.00")
    expense = totals["expense"] or Decimal("0.00")

    all_time = base.aggregate(
        income=Sum("amount", filter=Q(operation_type=Operation.OperationType.INCOME)),
        expense=Sum(
            "amount", filter=Q(operation_type=Operation.OperationType.EXPENSE)
        ),
    )
    initial = (
        Account.objects.filter(user=request.user, is_active=True).aggregate(
            total=Sum("initial_balance")
        )["total"]
        or Decimal("0.00")
    )
    balance = (
        initial + (all_time["income"] or Decimal("0.00"))
        - (all_time["expense"] or Decimal("0.00"))
    )

    budgets = list(
        Budget.objects.filter(user=request.user, period_start=period).select_related(
            "category"
        )
    )
    spent_by_category = {
        row["category_id"]: row["total"]
        for row in month_ops.filter(
            operation_type=Operation.OperationType.EXPENSE,
            category_id__in=[budget.category_id for budget in budgets],
        )
        .values("category_id")
        .annotate(total=Sum("amount"))
    }
    budget_rows = []
    for budget in budgets:
        spent = spent_by_category.get(budget.category_id, Decimal("0.00"))
        percent = (
            round(float(spent) / float(budget.limit_amount) * 100)
            if budget.limit_amount
            else 0
        )
        budget_rows.append(
            {
                "budget": budget,
                "spent": spent,
                "percent": percent,
                "bar_percent": min(percent, 100),
                "over": spent > budget.limit_amount,
            }
        )

    category_rows = []
    raw_categories = (
        month_ops.filter(operation_type=Operation.OperationType.EXPENSE)
        .values("category__name", "category__color")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    for row in raw_categories:
        percent = round(float(row["total"]) / float(expense) * 100) if expense else 0
        category_rows.append(
            {
                "name": row["category__name"],
                "color": row["category__color"],
                "total": row["total"],
                "percent": percent,
            }
        )

    recent_operations = base.select_related("category", "account")[:8]
    advice = build_budget_advice(income, expense, budget_rows, category_rows)

    context.update(
        {
            "income": income,
            "expense": expense,
            "balance": balance,
            "budget_rows": budget_rows,
            "category_rows": category_rows[:6],
            "recent_operations": recent_operations,
            "advice": advice,
            "has_accounts": Account.objects.filter(
                user=request.user, is_active=True
            ).exists(),
        }
    )
    return render(request, "finance/dashboard.html", context)


@login_required
def operation_list(request):
    qs = (
        Operation.objects.filter(user=request.user, is_deleted=False)
        .select_related("category", "account")
    )
    operation_type = request.GET.get("type", "")
    category_id = request.GET.get("category", "")
    query = request.GET.get("q", "").strip()

    if operation_type in (Operation.OperationType.INCOME, Operation.OperationType.EXPENSE):
        qs = qs.filter(operation_type=operation_type)
    if category_id.isdigit():
        qs = qs.filter(category_id=int(category_id))
    if query:
        qs = qs.filter(Q(description__icontains=query) | Q(category__name__icontains=query))

    page_obj = Paginator(qs, 15).get_page(request.GET.get("page"))
    context = {
        "page_obj": page_obj,
        "operations": page_obj.object_list,
        "categories": Category.objects.filter(user=request.user),
        "types": Operation.OperationType.choices,
        "selected_type": operation_type,
        "selected_category": category_id,
        "query": query,
    }
    return render(request, "finance/operation_list.html", context)


@login_required
def operation_create(request):
    if not Account.objects.filter(user=request.user, is_active=True).exists():
        messages.info(request, "Сначала добавьте хотя бы один счёт.")
        return redirect("finance:account_list")
    if not Category.objects.filter(user=request.user).exists():
        messages.info(request, "Сначала добавьте категории.")
        return redirect("finance:category_list")

    form = OperationForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        operation = form.save(commit=False)
        operation.user = request.user
        ai_used = False
        if operation.category_id is None:
            suggestion = suggest_category(
                operation.description, request.user, operation.operation_type
            )
            operation.category = suggestion.category or get_fallback_category(
                request.user, operation.operation_type
            )
            if operation.category is None:
                form.add_error(
                    "category", "Не удалось подобрать категорию. Выберите вручную."
                )
                return render(
                    request,
                    "finance/operation_form.html",
                    {"form": form, "title": "Новая операция"},
                )
            operation.created_by_ai = True
            operation.ai_confidence = Decimal(str(round(suggestion.confidence, 3)))
            ai_used = True
            ai_source = suggestion.source
        operation.save()
        if ai_used:
            AISuggestion.objects.create(
                user=request.user,
                operation=operation,
                input_text=operation.description,
                suggested_category=operation.category,
                confidence=operation.ai_confidence,
                source=ai_source,
                accepted=True,
            )
        messages.success(
            request,
            "Операция добавлена."
            + (" Категория подобрана автоматически." if ai_used else ""),
        )
        return redirect("finance:dashboard")

    return render(
        request,
        "finance/operation_form.html",
        {"form": form, "title": "Новая операция"},
    )


@login_required
@require_POST
def operation_delete(request, pk: int):
    operation = get_object_or_404(Operation, pk=pk, user=request.user)
    operation.is_deleted = True
    operation.save(update_fields=["is_deleted"])
    messages.success(request, "Операция удалена.")
    return redirect(request.POST.get("next") or "finance:operation_list")


@login_required
def budget_list(request):
    period = _parse_month(request.GET.get("month"))
    context = _month_context(period)
    start, end = _month_bounds(period)

    budgets = list(
        Budget.objects.filter(user=request.user, period_start=period).select_related(
            "category"
        )
    )
    month_ops = Operation.objects.filter(
        user=request.user,
        is_deleted=False,
        occurred_at__gte=start,
        occurred_at__lt=end,
        operation_type=Operation.OperationType.EXPENSE,
    )
    spent_by_category = {
        row["category_id"]: row["total"]
        for row in month_ops.values("category_id").annotate(total=Sum("amount"))
    }
    rows = []
    total_limit = Decimal("0.00")
    total_spent = Decimal("0.00")
    for budget in budgets:
        spent = spent_by_category.get(budget.category_id, Decimal("0.00"))
        percent = (
            round(float(spent) / float(budget.limit_amount) * 100)
            if budget.limit_amount
            else 0
        )
        total_limit += budget.limit_amount
        total_spent += spent
        rows.append(
            {
                "budget": budget,
                "spent": spent,
                "percent": percent,
                "bar_percent": min(percent, 100),
                "over": spent > budget.limit_amount,
                "left": budget.limit_amount - spent,
            }
        )

    form = BudgetForm(request.POST or None, user=request.user, initial_period=period)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Лимит сохранён.")
        return redirect(f"{request.path}?month={period:%Y-%m}")

    context.update(
        {
            "rows": rows,
            "form": form,
            "total_limit": total_limit,
            "total_spent": total_spent,
            "has_categories": Category.objects.filter(
                user=request.user, kind=Category.Kind.EXPENSE
            ).exists(),
        }
    )
    return render(request, "finance/budget_list.html", context)


@login_required
def category_list(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        category = form.save(commit=False)
        category.user = request.user
        category.save()
        messages.success(request, "Категория добавлена.")
        return redirect("finance:category_list")

    categories = Category.objects.filter(user=request.user).order_by("kind", "name")
    return render(
        request,
        "finance/category_list.html",
        {"categories": categories, "form": form},
    )


@login_required
def account_list(request):
    form = AccountForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        account = form.save(commit=False)
        account.user = request.user
        account.save()
        messages.success(request, "Счёт добавлен.")
        return redirect("finance:account_list")

    accounts = Account.objects.filter(user=request.user).annotate(
        income=Sum(
            "operations__amount",
            filter=Q(
                operations__operation_type=Operation.OperationType.INCOME,
                operations__is_deleted=False,
            ),
        ),
        expense=Sum(
            "operations__amount",
            filter=Q(
                operations__operation_type=Operation.OperationType.EXPENSE,
                operations__is_deleted=False,
            ),
        ),
    )
    rows = [
        {
            "account": account,
            "balance": account.initial_balance
            + (account.income or Decimal("0.00"))
            - (account.expense or Decimal("0.00")),
        }
        for account in accounts
    ]
    return render(
        request,
        "finance/account_list.html",
        {"rows": rows, "form": form},
    )


@login_required
@require_POST
def api_suggest_category(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Некорректный JSON."}, status=400)

    description = str(payload.get("description", "")).strip()
    operation_type = payload.get("operation_type", Operation.OperationType.EXPENSE)
    if operation_type not in (
        Operation.OperationType.INCOME,
        Operation.OperationType.EXPENSE,
    ):
        return JsonResponse({"error": "Неизвестный тип операции."}, status=400)
    if len(description) < 3:
        return JsonResponse(
            {"error": "Опишите операцию (минимум 3 символа)."}, status=400
        )

    suggestion = suggest_category(description, request.user, operation_type)
    return JsonResponse(
        {
            "category_id": suggestion.category.id if suggestion.category else None,
            "category": suggestion.category.name if suggestion.category else None,
            "confidence": round(suggestion.confidence, 2),
            "source": suggestion.source,
            "reason": suggestion.reason,
        }
    )


def health(request):
    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        database_ok = False
    return JsonResponse(
        {
            "status": "ok" if database_ok else "degraded",
            "service": "budgetkeeper",
            "version": "1.0.0",
            "database": "ok" if database_ok else "error",
        },
        status=200 if database_ok else 503,
    )


def api_ping(request):
    return JsonResponse({"status": "ok", "message": "pong"})


@login_required
def agent_page(request):
    """Страница диалога с ИИ-агентом."""
    history = list(
        AIMessage.objects.filter(user=request.user).order_by("created_at")[:20]
    )
    return render(request, "finance/agent.html", {"history": history})


@login_required
@require_POST
def agent_send(request):
    """Принимает сообщение, вызывает агента и возвращает ответ (JSON)."""
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Некорректный JSON."}, status=400)

    user_text = str(payload.get("message", "")).strip()
    if not user_text or len(user_text) > 1000:
        return JsonResponse(
            {"error": "Сообщение должно быть от 1 до 1000 символов."}, status=422
        )

    # История диалога из БД (последние 10 сообщений).
    history = list(
        AIMessage.objects.filter(user=request.user).order_by("created_at")[:10]
    )
    history = [{"role": m.role, "content": m.content} for m in history]

    answer = ask_agent(request.user, user_text, history)

    AIMessage.objects.create(user=request.user, role=AIMessage.Role.USER, content=user_text)
    AIMessage.objects.create(user=request.user, role=AIMessage.Role.ASSISTANT, content=answer)

    return JsonResponse({"reply": answer})
