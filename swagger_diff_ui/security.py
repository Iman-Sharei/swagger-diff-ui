"""Request guards for local-only schema-diff HTTP helpers."""

from __future__ import annotations

from urllib.parse import urlparse

from rest_framework.exceptions import PermissionDenied


def require_same_origin(request) -> None:
    """Block obvious cross-site browser calls to the debug HTTP helpers.

    Allows curl/scripts with no ``Sec-Fetch-Site`` / ``Origin`` headers so local
    tooling still works. Rejects ``Sec-Fetch-Site: cross-site`` and mismatched
    ``Origin`` / ``Referer`` hosts when those headers are present.
    """
    fetch_site = (request.META.get("HTTP_SEC_FETCH_SITE") or "").lower()
    if fetch_site == "cross-site":
        raise PermissionDenied("Cross-site requests are not allowed.")

    host = (request.get_host() or "").lower()
    origin = request.META.get("HTTP_ORIGIN")
    if origin:
        origin_host = (urlparse(origin).netloc or "").lower()
        if origin_host and origin_host != host:
            raise PermissionDenied("Cross-origin requests are not allowed.")
        return

    referer = request.META.get("HTTP_REFERER")
    if referer:
        referer_host = (urlparse(referer).netloc or "").lower()
        if referer_host and referer_host != host:
            raise PermissionDenied("Cross-origin requests are not allowed.")
