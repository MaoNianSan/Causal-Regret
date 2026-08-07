"""Repository-hygiene unit tests for the Exp1 presentation patch.

Covers: no mixed-scale shared colorbar in figure sources, gitignore policy
(paper candidate tracked; fast/full/transient status ignored), distinct
scientific/presentation lineage, and frozen-scientific hash invariance.
"""

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT.parent


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class TestNoMixedSharedScale(unittest.TestCase):
    """Figure sources must not draw a single heatmap/colorbar across metrics."""

    def test_no_heatmap_shared_colorbar_in_figure_sources(self) -> None:
        for name in ("plot_main.py", "plot_appendix.py"):
            source = (PROJECT_ROOT / name).read_text(encoding="utf-8")
            self.assertNotIn("imshow(", source, f"{name} must not use imshow")
            self.assertNotIn("pcolormesh(", source, f"{name} must not use pcolormesh")
            self.assertNotIn(".colorbar(", source, f"{name} must not use a colorbar")


class TestGitignorePolicy(unittest.TestCase):
    """Whitelisted paper candidate must be tracked; transient outputs ignored."""

    def _is_ignored(self, relpath: str) -> bool:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", relpath],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def test_gitignore_keeps_paper_candidate(self) -> None:
        self.assertFalse(
            self._is_ignored(
                "exp1_alignment_transfer/outputs/paper_candidate/figures/pdf/"
                "fig_exp1_alignment_transfer.pdf"
            ),
            "paper candidate figure must not be ignored",
        )
        self.assertFalse(
            self._is_ignored(
                "exp1_alignment_transfer/outputs/paper_candidate/exp1_promotion_manifest.json"
            ),
            "paper candidate manifest must not be ignored",
        )

    def test_gitignore_ignores_fast_full_outputs(self) -> None:
        for relpath in (
            "exp1_alignment_transfer/outputs/full/example.tmp",
            "exp1_alignment_transfer/outputs/fast/example.tmp",
            "exp1_alignment_transfer/outputs/full/logs/run.log",
            "exp1_alignment_transfer/outputs/full/cache/x.pkl",
        ):
            self.assertTrue(self._is_ignored(relpath), f"{relpath} should be ignored")

    def test_gitignore_ignores_transient_status(self) -> None:
        for name in (
            "calibration_status.json",
            "fast_run_status.json",
            "full_run_status.json",
            "fast_targeted_status.json",
            "full_targeted_status.json",
            "fast_validation_status.json",
            "full_validation_status.json",
            "paper_promotion_status.json",
        ):
            self.assertTrue(
                self._is_ignored(f"exp1_alignment_transfer/status/{name}"),
                f"transient status {name} should be ignored",
            )


class TestLineageSeparation(unittest.TestCase):
    """Figure metadata must carry distinct scientific and presentation lineage."""

    def test_scientific_and_presentation_lineage_are_distinct(self) -> None:
        meta_path = (
            PROJECT_ROOT
            / "outputs/full/figures/metadata/fig_exp1_alignment_transfer_metadata.json"
        )
        if not meta_path.exists():
            self.skipTest("full figure metadata not present locally")
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        scientific = payload.get("scientific_source_lineage", "")
        presentation = payload.get("presentation_source_lineage", "")
        self.assertTrue(
            scientific.startswith("tree:"), f"scientific lineage: {scientific}"
        )
        self.assertTrue(
            presentation.startswith("presentation:"),
            f"presentation lineage: {presentation}",
        )
        self.assertNotEqual(
            scientific, presentation, "scientific and presentation lineage must differ"
        )


class TestFrozenScientificInvariance(unittest.TestCase):
    """The paper candidate must match the hashes recorded in its artifact manifest."""

    def test_presentation_rebuild_does_not_touch_scientific_artifacts(self) -> None:
        manifest_path = (
            PROJECT_ROOT / "outputs/paper_candidate/metadata/artifact_manifest.json"
        )
        if not manifest_path.exists():
            self.skipTest("paper candidate artifact manifest not present locally")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        candidate_root = PROJECT_ROOT / "outputs/paper_candidate"
        artifacts = {item["path"]: item["sha256"] for item in manifest["artifacts"]}
        self.assertTrue(len(artifacts) > 0, "artifact manifest must not be empty")
        for relpath, expected in artifacts.items():
            artifact = candidate_root / relpath
            self.assertTrue(artifact.exists(), f"paper artifact missing: {relpath}")
            actual = _sha256(artifact)
            self.assertEqual(actual, expected, f"paper artifact changed: {relpath}")


if __name__ == "__main__":
    unittest.main()
