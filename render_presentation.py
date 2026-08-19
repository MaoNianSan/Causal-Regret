#!/usr/bin/env python
"""Thin orchestration CLI for CR-EXP-OUTPUT-V1 presentation previews."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from presentation import SPEC_ID
from presentation.common import PreviewLayout
from presentation.renderers import render_source, write_appendix_order, write_overview_table
from presentation.validation import validate_preview
from presentation_sources import iter_sources

ROOT = Path(__file__).resolve().parent
PUBLICATION_ROOT = ROOT / "publication" / SPEC_ID


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plan, render, or validate presentation-only previews.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "render", "validate"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--spec", default=SPEC_ID)
        sub.add_argument("--exp", default="all", choices=("all", "1", "2", "3", "4"))
        sub.add_argument(
            "--mode",
            default="preview",
            choices=("preview", "publication"),
            help="preview writes outside the repo; publication writes the canonical in-repo bundle",
        )
        sub.add_argument(
            "--preview-root",
            type=Path,
            help="required in preview mode; ignored in publication mode",
        )
    return parser


def _check_spec(value: str) -> None:
    if value != SPEC_ID:
        raise SystemExit(f"Unsupported output spec {value!r}; expected {SPEC_ID}")


def _output_root(args: argparse.Namespace) -> Path:
    if args.mode == "publication":
        return PUBLICATION_ROOT.resolve()
    if args.preview_root is None:
        raise SystemExit("--preview-root is required in preview mode")
    return args.preview_root.expanduser().resolve()


def _plan(args: argparse.Namespace) -> int:
    root = _output_root(args) if args.preview_root else Path("<PREVIEW_ROOT>")
    plans = [source.as_plan(root) for source in iter_sources(args.exp, mode=args.mode)]
    print(json.dumps({"spec_id": SPEC_ID, "mode": args.mode, "experiments": plans}, indent=2))
    return 0 if all(not plan["missing_source_files"] for plan in plans) else 2


def _render(args: argparse.Namespace) -> int:
    root = _output_root(args)
    summaries = []
    for source in iter_sources(args.exp, mode=args.mode):
        layout = PreviewLayout(root, source.experiment_id, source.run_id, mode=args.mode)
        # The overview table must exist before the renderer snapshots
        # artifact hashes into the presentation manifest.
        write_overview_table(layout, paper_result=source.paper_result)
        result = render_source(source, root)
        layout = result["layout"]
        write_appendix_order(layout, paper_result=source.paper_result)
        summaries.append(
            {
                "experiment_id": source.experiment_id,
                "run_id": source.run_id,
                "mode": args.mode,
                "source_run": str(source.source_run),
                "output_directory": str(layout.base),
            }
        )
    print(
        json.dumps(
            {
                "spec_id": SPEC_ID,
                "mode": args.mode,
                "paper_result": args.mode == "publication",
                "rendered": summaries,
            },
            indent=2,
        )
    )
    return 0


def _validate(args: argparse.Namespace) -> int:
    root = _output_root(args)
    reports = [
        validate_preview(source, root, mode=args.mode)
        for source in iter_sources(args.exp, mode=args.mode)
    ]
    print(json.dumps({"spec_id": SPEC_ID, "mode": args.mode, "passed": all(report["passed"] for report in reports), "reports": reports}, indent=2))
    return 0 if all(report["passed"] for report in reports) else 1


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    _check_spec(args.spec)
    if args.command == "plan":
        return _plan(args)
    if args.command == "render":
        return _render(args)
    return _validate(args)


if __name__ == "__main__":
    sys.exit(main())
