EXP1 rerun-ready source archive

Contents:
  source code, checks, output contracts, documentation, and lightweight local
  input placeholders.

Not included:
  completed fast/full numerical outputs, historical cloud run logs, executed
  result notebooks, caches, or virtual environments.

Validation performed before packaging:
  python code_check.py
  complete 264-combination smoke design
  current-schema raw-output rebuild
  self-check and one-worker detailed-trace audit

Start with:
  python code_check.py
  python reproduce_fast.py
  python self_check.py --mode fast
