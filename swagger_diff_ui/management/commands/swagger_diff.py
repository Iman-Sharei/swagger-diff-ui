"""CLI: compare live OpenAPI schema against a git baseline (CI-friendly)."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from swagger_diff_ui.exceptions import SchemaDiffError, SchemaDiffNotFound
from swagger_diff_ui.services.openapi_diff import annotate_breaking, diff_openapi
from swagger_diff_ui.services.schema_baseline import (
    generate_current_schema,
    generate_schema_at_ref,
    validate_git_ref,
)


class Command(BaseCommand):
    help = (
        "Diff the current OpenAPI schema against a git ref baseline. "
        "Use --fail-on-breaking (or --ci) to exit non-zero when breaking changes exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--ref",
            default="HEAD~1",
            help="Git baseline ref (branch, SHA, or relative like HEAD~1). Default: HEAD~1",
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--fail-on-breaking",
            action="store_true",
            help="Exit with code 1 when breaking changes are detected",
        )
        parser.add_argument(
            "--ci",
            action="store_true",
            help="CI mode: text summary + fail on breaking changes",
        )
        parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Ignore .schema-cache and regenerate the baseline schema",
        )

    def handle(self, *args, **options):
        ref = options["ref"]
        fmt = options["format"]
        fail_on_breaking = bool(options["fail_on_breaking"] or options["ci"])
        if options["ci"]:
            fmt = "text"

        try:
            ref = validate_git_ref(ref)
            baseline = generate_schema_at_ref(
                ref,
                use_cache=not options["no_cache"],
                require_local=False,
            )
            current = generate_current_schema()
            report = annotate_breaking(diff_openapi(baseline, current))
            report["baseline_ref"] = ref
        except SchemaDiffNotFound as exc:
            raise CommandError(str(exc.detail)) from exc
        except SchemaDiffError as exc:
            raise CommandError(str(exc.detail)) from exc
        except Exception as exc:  # noqa: BLE001 — surface unexpected failures for CI logs
            raise CommandError(f"Schema diff failed: {exc}") from exc

        if fmt == "json":
            self.stdout.write(json.dumps(report, indent=2, default=str))
        else:
            self._print_text(report)

        breaking_count = len(report.get("breaking") or [])
        if fail_on_breaking and breaking_count:
            self.stderr.write(
                self.style.ERROR(f"{breaking_count} breaking change(s) detected.")
            )
            # BaseCommand treats SystemExit oddly in some runners; raise SystemExit
            # after writing so CI gets a non-zero status.
            raise SystemExit(1)

    def _print_text(self, report: dict) -> None:
        summary = report.get("summary") or {}
        ref = report.get("baseline_ref", "?")
        self.stdout.write(f"Baseline: {ref}")
        self.stdout.write(
            "Summary: "
            f"added={summary.get('added', 0)} "
            f"removed={summary.get('removed', 0)} "
            f"updated={summary.get('updated', 0)} "
            f"unchanged={summary.get('unchanged', 0)} "
            f"breaking={summary.get('breaking', 0)}"
        )

        breaking = report.get("breaking") or []
        if not breaking:
            self.stdout.write(self.style.SUCCESS("No breaking changes."))
            return

        self.stdout.write("")
        self.stdout.write("Breaking changes:")
        for item in breaking:
            op = item.get("operation") or "(schema)"
            msg = item.get("message") or item.get("kind")
            self.stdout.write(f"  • [{op}] {msg}")
