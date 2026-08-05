# Exp1 V2 Test Report

- `python -m unittest discover -s tests -p 'test_*.py' -v` -> 10/10 OK
- Added: `tests/test_main_figure_headers.py`, `tests/test_presentation_hygiene.py`
- `python -m compileall -q config.py calibrate.py main.py targeted.py self_check.py plot_main.py plot_appendix.py promote.py cleanup.py src tests` -> exit 0
- `git diff --check` -> exit 0
