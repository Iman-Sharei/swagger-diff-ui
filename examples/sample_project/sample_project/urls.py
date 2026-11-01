from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from sample_project.views import HelloView

urlpatterns = [
    path("api/hello/", HelloView.as_view(), name="hello"),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/", include("swagger_diff_ui.urls")),
]
