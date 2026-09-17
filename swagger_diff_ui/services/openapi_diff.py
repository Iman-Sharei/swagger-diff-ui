"""Semantic OpenAPI diff (paths/operations + components.schemas)."""

from __future__ import annotations

from typing import Any

HTTP_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _is_obj(value: Any) -> bool:
    return isinstance(value, dict)


def _stable_stringify(value: Any) -> str:
    if value is None or isinstance(value, (bool, int, float, str)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ",".join(_stable_stringify(v) for v in value) + "]"
    if isinstance(value, dict):
        keys = sorted(value.keys())
        return "{" + ",".join(f"{k!r}:{_stable_stringify(value[k])}" for k in keys) + "}"
    return repr(value)


def _deep_equal(a: Any, b: Any) -> bool:
    return _stable_stringify(a) == _stable_stringify(b)


def _op_key(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


def _collect_operations(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path, path_item in (spec.get("paths") or {}).items():
        if not _is_obj(path_item):
            continue
        for method in HTTP_METHODS:
            op = path_item.get(method)
            if not _is_obj(op):
                continue
            out[_op_key(method, path)] = {
                "method": method.upper(),
                "path": path,
                "operation": op,
            }
    return out


def _collect_schemas(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    schemas = ((spec.get("components") or {}).get("schemas")) or {}
    return {name: schema for name, schema in schemas.items() if _is_obj(schema)}


def _required_set(schema: dict[str, Any] | None) -> set[str]:
    if not schema:
        return set()
    req = schema.get("required")
    if not isinstance(req, list):
        return set()
    return {x for x in req if isinstance(x, str)}


def _properties(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not schema:
        return {}
    props = schema.get("properties")
    return props if _is_obj(props) else {}


def _type_label(schema: Any) -> str:
    if not _is_obj(schema):
        return str(schema)
    if isinstance(schema.get("$ref"), str):
        return schema["$ref"]
    t = schema.get("type")
    if isinstance(t, str):
        if t == "array" and _is_obj(schema.get("items")):
            return f"array<{_type_label(schema['items'])}>"
        return t
    for key in ("allOf", "oneOf", "anyOf"):
        if isinstance(schema.get(key), list):
            return key
    return "object"


def _diff_prop_definition(
    key: str,
    before: Any,
    after: Any,
    prop_path: str,
) -> list[dict[str, Any]]:
    """Explain how an existing property's schema changed (not add/remove)."""
    changes: list[dict[str, Any]] = []
    if not _is_obj(before) or not _is_obj(after):
        changes.append(
            {
                "path": prop_path,
                "kind": "value_changed",
                "effect": "update",
                "target": key,
                "message": f'Property "{key}" updated',
                "before": before,
                "after": after,
            }
        )
        return changes

    bt, at = _type_label(before), _type_label(after)
    if bt != at:
        changes.append(
            {
                "path": prop_path,
                "kind": "type_changed",
                "effect": "update",
                "target": key,
                "message": f'Property "{key}" type changed: {bt} → {at}',
                "before": before,
                "after": after,
            }
        )

    if before.get("$ref") != after.get("$ref") and (
        isinstance(before.get("$ref"), str) or isinstance(after.get("$ref"), str)
    ):
        changes.append(
            {
                "path": f"{prop_path}.$ref",
                "kind": "schema_ref_changed",
                "effect": "update",
                "target": key,
                "message": f'Property "{key}" $ref changed: {before.get("$ref")} → {after.get("$ref")}',
                "before": before.get("$ref"),
                "after": after.get("$ref"),
            }
        )

    before_enum = before.get("enum") if isinstance(before.get("enum"), list) else None
    after_enum = after.get("enum") if isinstance(after.get("enum"), list) else None
    if before_enum is not None or after_enum is not None:
        before_set = set(before_enum or [])
        after_set = set(after_enum or [])
        for val in sorted(after_set - before_set, key=str):
            changes.append(
                {
                    "path": f"{prop_path}.enum",
                    "kind": "added",
                    "effect": "new",
                    "target": key,
                    "message": f'Property "{key}" enum value added: {val!r}',
                    "after": val,
                }
            )
        for val in sorted(before_set - after_set, key=str):
            changes.append(
                {
                    "path": f"{prop_path}.enum",
                    "kind": "removed",
                    "effect": "removed",
                    "target": key,
                    "message": f'Property "{key}" enum value removed: {val!r}',
                    "before": val,
                }
            )

    for field in ("format", "nullable", "default", "description", "minimum", "maximum", "minLength", "maxLength"):
        if not _deep_equal(before.get(field), after.get(field)):
            changes.append(
                {
                    "path": f"{prop_path}.{field}",
                    "kind": "value_changed",
                    "effect": "update",
                    "target": key,
                    "message": (
                        f'Property "{key}" {field} changed: '
                        f"{before.get(field)!r} → {after.get(field)!r}"
                    ),
                    "before": before.get(field),
                    "after": after.get(field),
                }
            )

    if before.get("properties") or after.get("properties"):
        changes.extend(_diff_object_props(before, after, prop_path))

    if before.get("items") or after.get("items"):
        if not _deep_equal(before.get("items"), after.get("items")):
            bi, ai = before.get("items"), after.get("items")
            if _is_obj(bi) and _is_obj(ai) and (bi.get("properties") or ai.get("properties")):
                changes.extend(_diff_object_props(bi, ai, f"{prop_path}.items"))
            else:
                changes.append(
                    {
                        "path": f"{prop_path}.items",
                        "kind": "value_changed",
                        "effect": "update",
                        "target": key,
                        "message": f'Property "{key}" array items schema updated',
                        "before": bi,
                        "after": ai,
                    }
                )

    if not changes and not _deep_equal(before, after):
        changes.append(
            {
                "path": prop_path,
                "kind": "value_changed",
                "effect": "update",
                "target": key,
                "message": f'Property "{key}" schema updated',
                "before": before,
                "after": after,
            }
        )
    return changes


def _diff_object_props(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    base_path: str,
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    before_props = _properties(before)
    after_props = _properties(after)
    before_req = _required_set(before)
    after_req = _required_set(after)
    all_keys = sorted(set(before_props) | set(after_props))

    for key in all_keys:
        prop_path = f"{base_path}.properties.{key}"
        had = key in before_props
        has = key in after_props
        if not had and has:
            changes.append(
                {
                    "path": prop_path,
                    "kind": "added",
                    "effect": "new",
                    "target": key,
                    "message": f'Added property "{key}" ({_type_label(after_props[key])})',
                    "after": after_props[key],
                }
            )
            if key in after_req:
                changes.append(
                    {
                        "path": f"{base_path}.required.{key}",
                        "kind": "required_changed",
                        "effect": "update",
                        "target": key,
                        "message": f'Property "{key}" is now required',
                        "before": False,
                        "after": True,
                    }
                )
            continue
        if had and not has:
            changes.append(
                {
                    "path": prop_path,
                    "kind": "removed",
                    "effect": "removed",
                    "target": key,
                    "message": f'Removed property "{key}" ({_type_label(before_props[key])})',
                    "before": before_props[key],
                }
            )
            continue

        b, a = before_props[key], after_props[key]
        if not _deep_equal(b, a):
            changes.extend(_diff_prop_definition(key, b, a, prop_path))

        was_req, is_req = key in before_req, key in after_req
        if was_req != is_req:
            changes.append(
                {
                    "path": f"{base_path}.required.{key}",
                    "kind": "required_changed",
                    "effect": "update",
                    "target": key,
                    "message": (
                        f'Property "{key}" updated: optional → required'
                        if is_req
                        else f'Property "{key}" updated: required → optional'
                    ),
                    "before": was_req,
                    "after": is_req,
                }
            )
    return changes


def _diff_schemas(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    base_path: str,
) -> list[dict[str, Any]]:
    if _deep_equal(before, after):
        return []
    if before is None and after is not None:
        return [
            {
                "path": base_path,
                "kind": "added",
                "message": f"Schema added ({_type_label(after)})",
                "after": after,
            }
        ]
    if before is not None and after is None:
        return [
            {
                "path": base_path,
                "kind": "removed",
                "message": f"Schema removed ({_type_label(before)})",
                "before": before,
            }
        ]
    assert before is not None and after is not None
    changes = _diff_object_props(before, after, base_path)
    for field in ("description", "nullable", "format", "enum", "default"):
        if not _deep_equal(before.get(field), after.get(field)):
            changes.append(
                {
                    "path": f"{base_path}.{field}",
                    "kind": "value_changed",
                    "message": f"{field} changed",
                    "before": before.get(field),
                    "after": after.get(field),
                }
            )
    if not changes and not _deep_equal(before, after):
        changes.append(
            {
                "path": base_path,
                "kind": "value_changed",
                "message": "Schema definition changed",
                "before": before,
                "after": after,
            }
        )
    return changes


def _param_id(param: dict[str, Any]) -> str:
    return f"{param.get('in', '')}:{param.get('name', '')}"


def _diff_parameters(before_op: dict[str, Any], after_op: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    before_params = [p for p in (before_op.get("parameters") or []) if _is_obj(p)]
    after_params = [p for p in (after_op.get("parameters") or []) if _is_obj(p)]
    before_map = {_param_id(p): p for p in before_params}
    after_map = {_param_id(p): p for p in after_params}
    for key in sorted(set(before_map) | set(after_map)):
        b, a = before_map.get(key), after_map.get(key)
        location, _, name = key.partition(":")
        if b is None and a is not None:
            changes.append(
                {
                    "path": f"parameters.{key}",
                    "kind": "added",
                    "message": f'Added {location} parameter "{name}"',
                    "after": a,
                }
            )
        elif b is not None and a is None:
            changes.append(
                {
                    "path": f"parameters.{key}",
                    "kind": "removed",
                    "message": f'Removed {location} parameter "{name}"',
                    "before": b,
                }
            )
        elif b is not None and a is not None and not _deep_equal(b, a):
            if not _deep_equal(b.get("required"), a.get("required")):
                was_req = bool(b.get("required"))
                is_req = bool(a.get("required"))
                changes.append(
                    {
                        "path": f"parameters.{key}.required",
                        "kind": "required_changed",
                        "area": "parameter",
                        "effect": "update",
                        "target": name,
                        "message": (
                            f'Parameter "{name}" updated: '
                            + (
                                "optional → required"
                                if is_req and not was_req
                                else "required → optional"
                            )
                        ),
                        "before": b.get("required"),
                        "after": a.get("required"),
                    }
                )
            if not _deep_equal(b.get("schema"), a.get("schema")):
                nested = _diff_schemas(
                    b.get("schema") if _is_obj(b.get("schema")) else None,
                    a.get("schema") if _is_obj(a.get("schema")) else None,
                    f"parameters.{key}.schema",
                )
                changes.extend(
                    nested
                    or [
                        {
                            "path": f"parameters.{key}.schema",
                            "kind": "type_changed",
                            "message": f'Parameter "{name}" schema changed',
                            "before": b.get("schema"),
                            "after": a.get("schema"),
                        }
                    ]
                )
            elif not _deep_equal(b, a):
                changes.append(
                    {
                        "path": f"parameters.{key}",
                        "kind": "value_changed",
                        "message": f'Parameter "{name}" changed',
                        "before": b,
                        "after": a,
                    }
                )
    return changes


def _media_schema(content: Any) -> dict[str, Any] | None:
    if not _is_obj(content):
        return None
    json_mt = content.get("application/json")
    if _is_obj(json_mt) and _is_obj(json_mt.get("schema")):
        return json_mt["schema"]
    for mt in content.values():
        if _is_obj(mt) and _is_obj(mt.get("schema")):
            return mt["schema"]
    return None


def _extract_refs(value: Any, out: set[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _extract_refs(item, out)
        return
    if not _is_obj(value):
        return
    ref = value.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        out.add(ref.rsplit("/", 1)[-1])
    for child in value.values():
        _extract_refs(child, out)


def _diff_request_body(before_op: dict[str, Any], after_op: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    before_body = before_op.get("requestBody") if _is_obj(before_op.get("requestBody")) else None
    after_body = after_op.get("requestBody") if _is_obj(after_op.get("requestBody")) else None
    if before_body is None and after_body is not None:
        return [{"path": "requestBody", "kind": "added", "message": "Added requestBody", "after": after_body}]
    if before_body is not None and after_body is None:
        return [{"path": "requestBody", "kind": "removed", "message": "Removed requestBody", "before": before_body}]
    if before_body is None or after_body is None:
        return changes
    if not _deep_equal(before_body.get("required"), after_body.get("required")):
        changes.append(
            {
                "path": "requestBody.required",
                "kind": "required_changed",
                "message": (
                    "requestBody requiredness changed: "
                    f"{bool(before_body.get('required'))} → {bool(after_body.get('required'))}"
                ),
                "before": before_body.get("required"),
                "after": after_body.get("required"),
            }
        )
    before_schema = _media_schema(before_body.get("content"))
    after_schema = _media_schema(after_body.get("content"))
    if not _deep_equal(before_schema, after_schema):
        changes.extend(_diff_schemas(before_schema, after_schema, "requestBody.content.schema"))
    return changes


def _diff_responses(before_op: dict[str, Any], after_op: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    before_res = before_op.get("responses") if _is_obj(before_op.get("responses")) else {}
    after_res = after_op.get("responses") if _is_obj(after_op.get("responses")) else {}
    for code in sorted(set(before_res) | set(after_res)):
        b, a = before_res.get(code), after_res.get(code)
        if b is None and a is not None:
            changes.append(
                {
                    "path": f"responses.{code}",
                    "kind": "added",
                    "message": f"Added response status {code}",
                    "after": a,
                }
            )
        elif b is not None and a is None:
            changes.append(
                {
                    "path": f"responses.{code}",
                    "kind": "removed",
                    "message": f"Removed response status {code}",
                    "before": b,
                }
            )
        elif not _deep_equal(b, a):
            before_schema = _media_schema(b.get("content")) if _is_obj(b) else None
            after_schema = _media_schema(a.get("content")) if _is_obj(a) else None
            nested = _diff_schemas(before_schema, after_schema, f"responses.{code}.content.schema")
            changes.extend(
                nested
                or [
                    {
                        "path": f"responses.{code}",
                        "kind": "value_changed",
                        "message": f"Response {code} changed",
                        "before": b,
                        "after": a,
                    }
                ]
            )
    return changes


def _diff_operation_meta(before_op: dict[str, Any], after_op: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for field in ("summary", "description", "operationId", "deprecated", "tags"):
        if not _deep_equal(before_op.get(field), after_op.get(field)):
            changes.append(
                {
                    "path": field,
                    "kind": "value_changed",
                    "message": f"{field} changed",
                    "before": before_op.get(field),
                    "after": after_op.get(field),
                }
            )
    return changes


def _diff_operations(before_op: dict[str, Any], after_op: dict[str, Any]) -> list[dict[str, Any]]:
    return (
        _diff_operation_meta(before_op, after_op)
        + _diff_parameters(before_op, after_op)
        + _diff_request_body(before_op, after_op)
        + _diff_responses(before_op, after_op)
    )


def _tally(summary: dict[str, int], status: str) -> None:
    summary[status] = summary.get(status, 0) + 1


def diff_openapi(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Return DiffReport for two OpenAPI documents."""
    baseline_ops = _collect_operations(baseline)
    current_ops = _collect_operations(current)
    baseline_schemas = _collect_schemas(baseline)
    current_schemas = _collect_schemas(current)

    components: dict[str, Any] = {}
    for name in sorted(set(baseline_schemas) | set(current_schemas)):
        key = f"schemas.{name}"
        before, after = baseline_schemas.get(name), current_schemas.get(name)
        if before is None and after is not None:
            status, changes = "added", [
                {"path": key, "kind": "added", "message": f'Schema "{name}" added', "after": after}
            ]
        elif before is not None and after is None:
            status, changes = "removed", [
                {"path": key, "kind": "removed", "message": f'Schema "{name}" removed', "before": before}
            ]
        else:
            changes = _diff_schemas(before, after, key)
            status = "updated" if changes else "unchanged"
        components[key] = {"key": key, "name": name, "status": status, "changes": changes}

    schema_status = {diff["name"]: diff["status"] for diff in components.values()}

    paths: dict[str, Any] = {}
    for key in sorted(set(baseline_ops) | set(current_ops)):
        before, after = baseline_ops.get(key), current_ops.get(key)
        if before is None and after is not None:
            paths[key] = {
                "key": key,
                "method": after["method"],
                "path": after["path"],
                "status": "added",
                "changes": [
                    {
                        "path": key,
                        "kind": "added",
                        "message": f"Operation {key} added",
                        "after": after["operation"],
                    }
                ],
                "operation": after["operation"],
            }
            continue
        if before is not None and after is None:
            paths[key] = {
                "key": key,
                "method": before["method"],
                "path": before["path"],
                "status": "removed",
                "changes": [
                    {
                        "path": key,
                        "kind": "removed",
                        "message": f"Operation {key} removed",
                        "before": before["operation"],
                    }
                ],
                "operation": before["operation"],
                "baselineOperation": before["operation"],
            }
            continue

        assert before is not None and after is not None
        changes = _diff_operations(before["operation"], after["operation"])
        related: set[str] = set()
        _extract_refs(after["operation"], related)
        _extract_refs(before["operation"], related)
        related_keys: list[str] = []
        for schema_name in related:
            st = schema_status.get(schema_name)
            if st and st != "unchanged":
                related_keys.append(f"schemas.{schema_name}")
                schema_diff = components[f"schemas.{schema_name}"]
                for c in schema_diff["changes"]:
                    changes.append({**c, "message": f'[schema {schema_name}] {c["message"]}'})

        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for c in changes:
            cid = f'{c.get("path")}|{c.get("kind")}|{c.get("message")}'
            if cid in seen:
                continue
            seen.add(cid)
            unique.append(c)

        paths[key] = {
            "key": key,
            "method": after["method"],
            "path": after["path"],
            "status": "updated" if unique else "unchanged",
            "changes": unique,
            "operation": after["operation"],
            "baselineOperation": before["operation"],
            "relatedSchemaKeys": related_keys,
        }

    summary = {"added": 0, "removed": 0, "updated": 0, "unchanged": 0}
    for op in paths.values():
        _tally(summary, op["status"])

    return {"paths": paths, "components": components, "summary": summary}
