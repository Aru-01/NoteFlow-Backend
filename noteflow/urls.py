from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # API endpoints
    path("auth/", include("accounts.urls")),
    path("api/notes/", include("notes.urls")),
    # OpenAPI Documentation
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
