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

From this directory (still inside the parent git checkout):

```bash
python manage.py swagger_diff --ref HEAD~1 --format text
```

Baseline export creates a temporary worktree of the **repo root**, then runs this nested `manage.py` inside it. The chosen `--ref` must already contain `examples/sample_project/manage.py` (commits from before the sample was added will fail with a clear error).
