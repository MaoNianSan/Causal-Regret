"""Verify final Exp3 release archives and write release reports."""
from __future__ import annotations

from release_support import verify_release_packages, write_release_reports


def main() -> int:
    ok, errors = verify_release_packages()
    write_release_reports(errors)
    if not ok:
        print("RELEASE PACKAGE VERIFICATION FAILED")
        for error in errors:
            print(f"[FAIL] {error}")
        return 1
    print("RELEASE PACKAGE VERIFICATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
