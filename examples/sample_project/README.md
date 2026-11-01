# Sample project

Minimal Django + DRF app that wires `swagger-diff-ui`.

## Run

From the **repository root**:

```bash
pip install -e ".[dev]"
cd examples/sample_project
python manage.py runserver
```

Open http://127.0.0.1:8000/api/docs/

## CLI check

```bash
python manage.py swagger_diff --ref HEAD~1 --format text
```

Requires this sample directory (or the parent repo) to be a git checkout with at least two commits that change the OpenAPI surface.
