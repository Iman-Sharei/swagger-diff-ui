"""Guards for local schema-diff HTTP helpers."""

from __future__ import annotations

import pytest
from rest_framework.exceptions import PermissionDenied

from swagger_diff_ui.security import require_same_origin


class _FakeRequest:
    def __init__(self, host: str = "127.0.0.1:8000", **headers: str):
        self.META = {"HTTP_HOST": host}
        for key, value in headers.items():
            self.META[key] = value

    def get_host(self) -> str:
        return self.META.get("HTTP_HOST", "")


def test_same_origin_allows_plain_request():
    require_same_origin(_FakeRequest())


def test_same_origin_allows_matching_origin():
    require_same_origin(
        _FakeRequest(HTTP_ORIGIN="http://127.0.0.1:8000")
    )


def test_same_origin_blocks_cross_site_fetch():
    with pytest.raises(PermissionDenied):
        require_same_origin(_FakeRequest(HTTP_SEC_FETCH_SITE="cross-site"))


def test_same_origin_blocks_mismatched_origin():
    with pytest.raises(PermissionDenied):
        require_same_origin(_FakeRequest(HTTP_ORIGIN="https://evil.example"))


def test_same_origin_blocks_mismatched_referer():
    with pytest.raises(PermissionDenied):
        require_same_origin(_FakeRequest(HTTP_REFERER="https://evil.example/page"))
