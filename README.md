# 🔀 swagger-diff-ui

[![PyPI](https://img.shields.io/pypi/v/swagger-diff-ui.svg)](https://pypi.org/project/swagger-diff-ui/)
[![Python](https://img.shields.io/pypi/pyversions/swagger-diff-ui.svg)](https://pypi.org/project/swagger-diff-ui/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Drop-in Swagger UI for Django + DRF** that diffs your live OpenAPI schema against a **git branch or commit** — then paints every changed endpoint as **NEW · UPDATE · DELETE**.

No Node. No separate SPA. Same `/api/docs/` you already open — with a small baseline drawer on top.

![Schema diff UI showing NEW, UPDATE, and DELETE badges on Swagger endpoints](https://raw.githubusercontent.com/Iman-Sharei/swagger-diff-ui/main/docs/assets/schema-diff-preview.png)

*Pick a baseline → Compare → see what changed.*

---

## ✨ What you get

| | Feature | What it does |
|---|---------|----------------|
| 🌿 | **Branch / commit** selectors | Baseline from your real git history |
| ▶️ | **Compare** | Diff current schema vs that baseline |
| 🟢🟡🔴 | **NEW / UPDATE / DELETE** tags | On the left of every changed operation |
| 🎯 | **Changed only** | Hide unchanged APIs (toggle anytime) |
| 🔬 | **Field-level UPDATE** | Params, body, responses, schema props — colored dots |

> ⚙️ Baseline export uses a temporary **git worktree** + `manage.py spectacular`. Intended for **local / DEBUG** only.

---

## 📦 Requirements

- Python **3.10+**
- Django **4.2+**
- Django REST Framework
- [drf-spectacular](https://drf-spectacular.readthedocs.io/)
- A **git checkout** of your project (for branch/commit baselines)

---

## 🚀 Install

```bash
pip install swagger-diff-ui
```

### From GitHub

```bash
pip install "git+https://github.com/Iman-Sharei/swagger-diff-ui.git"
```

---

## 🔌 Wire into Django

Same idea as spectacular: **one app + a few routes**.

### 1️⃣ Add the app

```python
# settings — typically local / debug only
INSTALLED_APPS = [
    # ...
    "drf_spectacular",
    "swagger_diff_ui",
]
```

### 2️⃣ Keep spectacular’s schema + include our URLs

```python
# urls.py
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

urlpatterns = [
    # Real OpenAPI document (unchanged)
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),

    # Diff UI + helpers
    path("api/", include("swagger_diff_ui.urls")),
]
```

### 3️⃣ Open the docs

```text
http://127.0.0.1:8000/api/docs/
```

Done. ✅

---

## 🖱️ How to use

1. Open **`/api/docs/`**
2. In the dark drawer, pick a **baseline branch** or **commit**
3. Click **Compare**
4. Changed endpoints get **NEW / UPDATE / DELETE**
5. Open an **UPDATE** row for field-level diffs + colored Example Value dots
6. Use **Changed only** / **Show all APIs** and **Hide ▴** / **Show ▾**

⏱️ First compare for a given SHA can take a bit (worktree + schema export). Results cache under `.schema-cache/` — keep that folder in `.gitignore`.

---

## 🗺️ Routes

Assuming you included under `api/`:

| URL | Role |
|-----|------|
| `/api/docs/` | Swagger UI + schema-diff drawer |
| `/api/schema/` | Your real OpenAPI schema (**spectacular**) |
| `/api/swagger-diff/git-refs/` | Branches + recent commits |
| `/api/swagger-diff/diff/?ref=…` | Diff report vs baseline |
| `/api/swagger-diff/baseline/?ref=…` | Raw baseline OpenAPI (optional) |

Diff helpers live under `/api/swagger-diff/…` so they never collide with `/api/schema/`.

---

## 🔒 Safety notes

- Git baseline APIs are gated to **`DJANGO_ENV == "local"`** or **`DEBUG=True`**
- Do **not** expose these on production with `DEBUG=True`
- Prefer wiring `swagger_diff_ui` only in local / staging settings

---

## 🧪 Develop & test

```bash
pip install -e ".[dev]"
pytest -q
```

---

## 📄 License

[MIT](LICENSE) · made for Django + DRF teams who live in `/api/docs/`
