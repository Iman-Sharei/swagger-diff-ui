"""Package-local API exceptions (no host-project dependency)."""

from rest_framework import status
from rest_framework.exceptions import APIException


class SchemaDiffError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "SCHEMA_DIFF_ERROR"
    default_detail = "Schema diff request failed."


class SchemaDiffNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_code = "SCHEMA_DIFF_REF_NOT_FOUND"
    default_detail = "Git ref not found."
