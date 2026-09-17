"""Service-layer verification for git ref validation and OpenAPI differ."""

import pytest

from swagger_diff_ui.exceptions import SchemaDiffError
from swagger_diff_ui.services.openapi_diff import diff_openapi
from swagger_diff_ui.services.schema_baseline import validate_git_ref


def test_diff_marks_added_removed_and_schema_property_updates():
    baseline = {
        "openapi": "3.0.3",
        "paths": {
            "/users/": {
                "get": {
                    "summary": "List",
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/legacy/": {
                "get": {
                    "summary": "Legacy",
                    "responses": {"200": {"description": "ok"}},
                }
            },
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                    },
                }
            }
        },
    }
    current = {
        "openapi": "3.0.3",
        "paths": {
            "/users/": {
                "get": {
                    "summary": "List users",
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            },
                        }
                    },
                }
            },
            "/health/": {
                "get": {
                    "summary": "Health",
                    "responses": {"200": {"description": "ok"}},
                }
            },
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "required": ["id", "age"],
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                }
            }
        },
    }

    report = diff_openapi(baseline, current)

    assert report["paths"]["GET /health/"]["status"] == "added"
    assert report["paths"]["GET /legacy/"]["status"] == "removed"
    assert report["paths"]["GET /users/"]["status"] == "updated"
    assert any('parameter "q"' in c["message"] for c in report["paths"]["GET /users/"]["changes"])

    user = report["components"]["schemas.User"]
    assert user["status"] == "updated"
    assert any(c["kind"] == "added" and "age" in c["message"] for c in user["changes"])
    assert any(c["kind"] == "required_changed" and "age" in c["message"] for c in user["changes"])


@pytest.mark.parametrize(
    "ref",
    ["", " ", "../etc/passwd", "HEAD;rm", "feature branch", "a..b"],
)
def test_validate_git_ref_rejects_invalid(ref):
    with pytest.raises(SchemaDiffError) as exc:
        validate_git_ref(ref)
    assert exc.value.get_codes() == "SCHEMA_DIFF_INVALID_REF"

def test_validate_git_ref_accepts_safe_refs():
    assert validate_git_ref("HEAD") == "HEAD"
    assert validate_git_ref("origin/development") == "origin/development"
    assert validate_git_ref("abc123def") == "abc123def"


def test_param_requiredness_is_update_not_add_remove():
    baseline = {
        "openapi": "3.0.3",
        "paths": {
            "/x/": {
                "get": {
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    current = {
        "openapi": "3.0.3",
        "paths": {
            "/x/": {
                "get": {
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    report = diff_openapi(baseline, current)
    op = report["paths"]["GET /x/"]
    assert op["status"] == "updated"
    req_changes = [c for c in op["changes"] if c["kind"] == "required_changed"]
    assert req_changes
    assert req_changes[0].get("effect") == "update"
    assert "optional → required" in req_changes[0]["message"]


def test_property_add_and_remove_classified():
    baseline = {
        "openapi": "3.0.3",
        "paths": {},
        "components": {
            "schemas": {
                "Body": {
                    "type": "object",
                    "properties": {"languages": {"type": "array"}},
                }
            }
        },
    }
    current = {
        "openapi": "3.0.3",
        "paths": {},
        "components": {
            "schemas": {
                "Body": {
                    "type": "object",
                    "properties": {"language": {"type": "string"}},
                }
            }
        },
    }
    report = diff_openapi(baseline, current)
    body = report["components"]["schemas.Body"]
    assert body["status"] == "updated"
    kinds = {(c["kind"], c.get("target") or c.get("effect")) for c in body["changes"]}
    assert any(c["kind"] == "added" and c.get("target") == "language" for c in body["changes"])
    assert any(c["kind"] == "removed" and c.get("target") == "languages" for c in body["changes"])
