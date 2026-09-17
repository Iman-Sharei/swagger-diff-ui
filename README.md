# swagger-diff-ui

**Drop-in Swagger UI for Django + DRF** that compares your **current** OpenAPI schema against a **git branch or commit**, then paints endpoints as **NEW · UPDATE · DELETE**.

No Node. No separate SPA. Same `/api/docs/` page you already use — with a small baseline drawer on top.

---

## What you get

| In the UI | What it does |
|-----------|----------------|
| **Branch / commit** selectors | Pick a baseline from your git history |
| **Compare** | Diff current schema vs that baseline |
| **NEW / UPDATE / DELETE** tags | On the left of each changed operation |
| **Changed only** | Hide unchanged APIs (toggle back anytime) |
| **Field-level UPDATE** | Params, body, responses, schema props — green / amber / red |

> Baseline export uses a temporary **git worktree** + `manage.py spectacular`. Intended for **local / DEBUG** only.

---

## Requirements

- Python **3.10+**
- Django **4.2+**
- Django REST Framework
- [drf-spectacular](https://drf-spectacular.readthedocs.io/)
- A **git checkout** of your project (for branch/commit baselines)

---

## Install

### From PyPI (when published)

```bash
pip install swagger-diff-ui
```

### From GitHub

```bash
pip install "git+https://github.com/Iman-Sharei/swagger-diff-ui.git"
```

### Local editable (developing the package)

```bash
pip install -e /path/to/swagger-diff-ui
```

Or from the package root:

```bash
pip install -e ".[dev]"
```

---

## Wire into your Django project

Think of it like spectacular: **one app + a few URL routes**.

### 1. Add the app

```python
# settings — typically local / debug only
INSTALLED_APPS = [
    # ...
    "drf_spectacular",
    "swagger_diff_ui",
]
```

### 2. Keep spectacular’s schema endpoint

```python
# urls.py
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

urlpatterns = [
    # Real OpenAPI document (unchanged)
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),

    # Diff UI + helpers (docs live here)
    path("api/", include("swagger_diff_ui.urls")),
]
```

### 3. Open the docs

```text
http://127.0.0.1:8000/api/docs/
```

That’s it.

---

## How to use

1. Open **`/api/docs/`**
2. In the dark drawer, pick a **baseline branch** or **commit**
3. Click **Compare**
4. Changed endpoints get **NEW / UPDATE / DELETE**
5. Open an **UPDATE** operation to see field-level diffs and colored Example Value dots
6. Use **Changed only** / **Show all APIs** and **Hide ▴** / **Show ▾** on the drawer

First compare for a given SHA can take a bit (worktree + schema export). Results are cached under `.schema-cache/` in your project root — add that folder to `.gitignore` if it isn’t already.

---

## Routes

Assuming you included under `api/`:

| URL | Role |
|-----|------|
| `/api/docs/` | Swagger UI + schema-diff drawer |
| `/api/schema/` | Your real OpenAPI schema (**spectacular** — not owned by this package) |
| `/api/swagger-diff/git-refs/` | Branches + recent commits |
| `/api/swagger-diff/diff/?ref=<git-ref>` | Diff report vs baseline |
| `/api/swagger-diff/baseline/?ref=<git-ref>` | Raw baseline OpenAPI (optional) |

Diff helpers live under `/api/swagger-diff/…` so they never collide with `/api/schema/`.

---

## Safety notes

- Git baseline APIs are gated to **`DJANGO_ENV == "local"`** or **`DEBUG=True`**.
- Do **not** expose these endpoints on production with `DEBUG=True`.
- Prefer wiring `swagger_diff_ui` only in local / staging settings.

---

## Develop & test this package

```bash
cd swagger-diff-ui
pip install -e ".[dev]"
pytest -q
```

---

## License

[MIT](LICENSE)
