import numpy as np


def set_global_seed(seed: int):
    np.random.seed(int(seed))


def eps_schedule(
    t: int, eps0: float = 0.2, eps_min: float = 0.01, decay: float = 2000.0
) -> float:
    t = int(t)
    eps = eps_min + (eps0 - eps_min) * np.exp(-t / float(decay))
    return float(eps)


def mean_std(xs):
    xs = np.asarray(xs, dtype=float)
    return float(xs.mean()), float(xs.std(ddof=1) if xs.size > 1 else 0.0)
