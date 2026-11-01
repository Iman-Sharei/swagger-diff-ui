"""Public API views shipped by swagger-diff-ui."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from swagger_diff_ui.services.openapi_diff import diff_openapi
from swagger_diff_ui.services.schema_baseline import (
    generate_current_schema,
    generate_schema_at_ref,
    list_git_refs,
    validate_git_ref,
)


@extend_schema(exclude=True)
class SchemaGitRefsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        branch = request.query_params.get("branch") or None
        return Response(list_git_refs(branch=branch))


@extend_schema(exclude=True)
class SchemaBaselineView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        ref = validate_git_ref(request.query_params.get("ref") or "HEAD")
        return Response(generate_schema_at_ref(ref))


@extend_schema(exclude=True)
class SchemaDiffView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        ref = validate_git_ref(request.query_params.get("ref") or "HEAD")
        baseline = generate_schema_at_ref(ref)
        current = generate_current_schema()
        report = diff_openapi(baseline, current)
        report["baseline_ref"] = ref
        return Response(report)


@extend_schema(exclude=True)
class SwaggerDiffUIView(SpectacularSwaggerView):
    """Drop-in Swagger UI with branch/commit schema diff toolbar."""

    authentication_classes = []
    permission_classes = [AllowAny]
    template_name = "swagger_diff_ui/swagger.html"
