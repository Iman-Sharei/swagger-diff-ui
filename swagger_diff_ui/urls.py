from django.conf import settings
from django.urls import path

from swagger_diff_ui.views import (
    SchemaBaselineView,
    SchemaDiffView,
    SchemaGitRefsView,
    SwaggerDiffUIView,
)

# Must match the URL name of SpectacularAPIView (default: "api-schema").
# Override with SWAGGER_DIFF_SCHEMA_URL_NAME if your schema route uses another name.
_SCHEMA_URL_NAME = getattr(settings, "SWAGGER_DIFF_SCHEMA_URL_NAME", "api-schema")

# Under project include prefix `api/` these become:
#   /api/swagger-diff/git-refs/
#   /api/swagger-diff/baseline/
#   /api/swagger-diff/diff/
#   /api/docs/
# (does not touch /api/schema/ — that stays spectacular)
urlpatterns = [
    path("swagger-diff/git-refs/", SchemaGitRefsView.as_view(), name="swagger-diff-git-refs"),
    path("swagger-diff/baseline/", SchemaBaselineView.as_view(), name="swagger-diff-baseline"),
    path("swagger-diff/diff/", SchemaDiffView.as_view(), name="swagger-diff-diff"),
    path(
        "docs/",
        SwaggerDiffUIView.as_view(url_name=_SCHEMA_URL_NAME),
        name="swagger-diff-ui",
    ),
]
