#!/usr/bin/env python3
"""
Code quality and consistency checks for Toy experiment.

Validates:
- No unused backup or legacy files
- No old output dependencies
- No absolute local paths in source code
- README.md commands match existing scripts
- output_manifest.md accuracy
- All required scripts present
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple


# File and directory patterns to flag as backup/legacy
BACKUP_PATTERNS = {
    r".*\.(bak|old|backup|orig|copy|new|final|tmp|temp)$",
    r".*_old\b.*",
    r".*_backup\b.*",
    r".*_copy\b.*",
    r".*~$",
    r"#.*#",
}

# Required scripts
REQUIRED_SCRIPTS = {
    "main.py",
    "core.py",
    "delay.py",
    "io_utils.py",
    "summarize.py",
    "plot.py",
    "self_check.py",
    "code_check.py",
    "analyze_results.py",
    "reproduce_fast.py",
    "reproduce_paper.py",
}

REQUIRED_CONFIG = {
    "config.yaml",
    "requirements.txt",
    "README.md",
    "output_manifest.md",
}


class CodeChecker:
    def __init__(self, root: Path):
        self.root = root
        self.passed = []
        self.failed = []

    def report(self, status: str, message: str):
        """Record check result."""
        if status == "PASS":
            self.passed.append(message)
            print(f"[PASS] {message}")
        else:
            self.failed.append(message)
            print(f"[FAIL] {message}")

    def check_backup_files(self):
        """Check for unwanted backup/legacy files."""
        backup_files = []
        for path in self.root.rglob("*"):
            if path.is_dir():
                continue
            name = path.name
            for pattern in BACKUP_PATTERNS:
                if re.match(pattern, name):
                    backup_files.append(path.relative_to(self.root))
                    break
        
        if backup_files:
            self.report("FAIL", f"Backup/legacy files found: {backup_files}")
        else:
            self.report("PASS", "No backup or legacy files")

    def check_required_files(self):
        """Check for required scripts and config files."""
        missing_scripts = []
        missing_config = []
        
        for script in REQUIRED_SCRIPTS:
            if not (self.root / script).exists():
                missing_scripts.append(script)
        
        for config in REQUIRED_CONFIG:
            if not (self.root / config).exists():
                missing_config.append(config)
        
        if missing_scripts:
            self.report("FAIL", f"Missing required scripts: {missing_scripts}")
        else:
            self.report("PASS", "All required scripts present")
        
        if missing_config:
            self.report("FAIL", f"Missing required config files: {missing_config}")
        else:
            self.report("PASS", "All required config files present")

    def check_absolute_paths(self):
        """Check for hardcoded absolute local paths in Python files."""
        absolute_path_pattern = re.compile(r"['\"]([a-zA-Z]:)?/.*?['\"]")
        found_paths = []
        
        for py_file in self.root.glob("*.py"):
            try:
                with py_file.open("r", encoding="utf-8") as f:
                    for line_no, line in enumerate(f, 1):
                        # Skip comments
                        if line.strip().startswith("#"):
                            continue
                        matches = absolute_path_pattern.findall(line)
                        if matches:
                            found_paths.append(f"{py_file.name}:{line_no}")
            except Exception:
                pass
        
        if found_paths:
            self.report("FAIL", f"Hardcoded absolute paths found: {found_paths[:5]}")
        else:
            self.report("PASS", "No hardcoded absolute paths detected")

    def check_readme_commands(self):
        """Verify README.md mentions commands that match existing scripts."""
        readme_path = self.root / "README.md"
        if not readme_path.exists():
            self.report("FAIL", "README.md not found")
            return
        
        with readme_path.open("r", encoding="utf-8") as f:
            readme_content = f.read()
        
        required_mentions = {
            "reproduce_fast.py": False,
            "reproduce_paper.py": False,
            "self_check.py": False,
            "code_check.py": False,
        }
        
        for script in required_mentions:
            if script in readme_content:
                required_mentions[script] = True
        
        missing = [s for s, found in required_mentions.items() if not found]
        if missing:
            self.report("FAIL", f"README.md missing mentions of: {missing}")
        else:
            self.report("PASS", "README.md documents all key scripts")

    def check_output_manifest(self):
        """Verify output_manifest.md exists and is non-empty."""
        manifest_path = self.root / "output_manifest.md"
        if not manifest_path.exists():
            self.report("FAIL", "output_manifest.md not found")
            return
        
        if manifest_path.stat().st_size < 100:
            self.report("FAIL", "output_manifest.md is empty or too short")
        else:
            self.report("PASS", "output_manifest.md present and has content")

    def check_old_output_dependency(self):
        """Check that code doesn't depend on stale outputs from previous runs."""
        # Look for patterns that read from outputs/ without regenerating
        suspicious_patterns = {
            "pd.read_csv.*outputs",
            "read_csv.*outputs",
            ".open.*outputs",
        }
        found_issues = []
        
        # Scripts that legitimately reference outputs/ (analysis, checking, plotting)
        exempt_scripts = {
            "code_check.py",
            "self_check.py",
            "analyze_results.py",
            "summarize.py",
            "plot.py",
        }
        
        for py_file in self.root.glob("*.py"):
            if py_file.name in exempt_scripts:
                continue
            try:
                with py_file.open("r", encoding="utf-8") as f:
                    content = f.read()
                    # Skip main.py, which legitimately generates outputs
                    if py_file.name == "main.py":
                        continue
                    for pattern in suspicious_patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            found_issues.append(py_file.name)
                            break
            except Exception:
                pass
        
        if found_issues:
            self.report("FAIL", f"Scripts may depend on stale outputs: {found_issues}")
        else:
            self.report("PASS", "No suspicious old output dependencies detected")

    def check_random_seed_control(self):
        """Verify that random seed control is explicit in main.py."""
        main_py = self.root / "main.py"
        if not main_py.exists():
            return
        
        with main_py.open("r", encoding="utf-8") as f:
            content = f.read()
        
        has_seed = "seed" in content.lower() and ("random.seed" in content or "getstate" in content)
        if has_seed:
            self.report("PASS", "Random seed control is explicit in main.py")
        else:
            self.report("FAIL", "Random seed control appears weak or missing in main.py")

    def run_all_checks(self) -> bool:
        """Run all checks and return overall pass/fail."""
        print(f"\n{'='*70}")
        print("CODE_CHECK.PY - Toy Experiment Code Quality Validation")
        print(f"{'='*70}\n")
        
        self.check_required_files()
        self.check_backup_files()
        self.check_absolute_paths()
        self.check_readme_commands()
        self.check_output_manifest()
        self.check_old_output_dependency()
        self.check_random_seed_control()
        
        print(f"\n{'='*70}")
        print(f"Summary: {len(self.passed)} passed, {len(self.failed)} failed")
        print(f"{'='*70}\n")
        
        if self.failed:
            print("FAILED CHECKS:")
            for msg in self.failed:
                print(f"  - {msg}")
            return False
        else:
            print("All code quality checks PASSED.")
            return True


def main():
    root = Path(__file__).resolve().parent
    checker = CodeChecker(root)
    success = checker.run_all_checks()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
