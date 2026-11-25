from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("operations/", views.operation_list, name="operation_list"),
    path("operations/add/", views.operation_create, name="operation_create"),
    path(
        "operations/<int:pk>/delete/",
        views.operation_delete,
        name="operation_delete",
    ),
    path("budgets/", views.budget_list, name="budget_list"),
    path("categories/", views.category_list, name="category_list"),
    path("wallets/", views.account_list, name="account_list"),
    path("api/suggest-category/", views.api_suggest_category, name="api_suggest_category"),
    path("api/ping/", views.api_ping, name="api_ping"),
    path("health/", views.health, name="health"),
]
