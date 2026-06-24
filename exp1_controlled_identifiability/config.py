"""Execution-scale configuration for EXP1.

The experiment definition itself lives in ``src.delay.scenario_definitions`` so
that the declared information structure and finite-horizon delay calibration
are executable rather than duplicated constants.
"""

K = 10
T = 5000
SEEDS = list(range(30))
D_MAX = 100
FAST_T = T
FAST_SEEDS = [0, 1, 2]

# Paper-facing uncertainty contract for the 30 shared simulation seeds.
N_BOOTSTRAP = 2000
CI_LEVEL = 0.95
