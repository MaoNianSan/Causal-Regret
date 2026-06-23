"""Build final upload-ready archives for the promoted Exp3 full run."""
from __future__ import annotations

from release_support import build_release_packages


def main() -> int:
    build_release_packages()
    print("UPLOAD PACKAGES BUILT")
    print("exp3_long_term_recoverability_upload_ready_code.zip")
    print("exp3_long_term_recoverability_reproducibility_manifest.zip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
