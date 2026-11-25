from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("profile/", views.profile, name="profile"),
    path("password-reset/", views.password_reset_request, name="password_reset"),
    path(
        "password-reset/<str:token>/",
        views.password_reset_confirm,
        name="password_reset_confirm",
    ),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("api/admin/stats/", views.admin_stats_api, name="admin_stats_api"),
]
