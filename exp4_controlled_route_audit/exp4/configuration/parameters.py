"""Immutable scientific parameters for Exp4 v2."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SharedDGPConfig:
    num_actions: int = 10
    state_dimension: int = 3
    target_mean_delay: int = 2
    maximum_candidate_delay: int = 20
    delay_state_coupling: float = 2.0
    feedback_noise_sd: float = 0.009
    root_seed: int = 2026080604


@dataclass(frozen=True)
class ModuleAConfig:
    horizon: int = 5000
    warmup: int = 250
    evaluation_seeds: tuple[int, ...] = tuple(range(100))
    route_label_rates: tuple[float, ...] = (0.0, 0.3, 0.7, 1.0)
    proxy_noise_sds: tuple[float, ...] = (0.0, 0.10, 0.25, 1.0)
    primary_proxy_noise_sd: float = 0.25


@dataclass(frozen=True)
class ModuleBConfig:
    horizon: int = 2000
    warmup: int = 100
    replications: int = 1000
    audit_evidence_rates: tuple[float, ...] = (0.10, 0.30, 0.50, 1.00)
    route_label_rate: float = 0.30
    proxy_noise_sd: float = 0.25
    ambiguity_slope: float = 1.5
    inclusion_lower_bound: float = 0.05
    inclusion_upper_bound: float = 0.95
    inclusion_rate_tolerance: float = 1e-8


@dataclass(frozen=True)
class CalibrationConfig:
    calibration_seeds: tuple[int, ...] = tuple(range(50_000, 50_020))
    proxy_calibration_noise_sd: float = 0.25
    delay_prior_smoothing: float = 1.0
    temporal_folds: int = 5
    minimum_training_support: int = 100
    audit_evidence_rate: float = 0.30
    affine_intercept: float = 0.20
    affine_slope: float = 1.50
    affine_noise_fraction: float = 0.10
    nonlinear_scale: float = 1.00
    variance_tolerance: float = 1e-14


@dataclass(frozen=True)
class ReportingConfig:
    confidence_level: float = 0.95
    bootstrap_seed: int = 2026080605
    zero_defect_tolerance: float = 1e-12
    raw_defect_epsilon: float = 1e-12
    route_audit_correlation_tolerance: float = 0.05
    paper_figure_width_in: float = 7.15
    paper_figure_height_in: float = 5.75
    paper_dpi: int = 300


SHARED_DGP = SharedDGPConfig()
MODULE_A = ModuleAConfig()
MODULE_B = ModuleBConfig()
CALIBRATION = CalibrationConfig()
REPORTING = ReportingConfig()


def parameter_payload() -> dict[str, Any]:
    return {
        "shared_dgp": asdict(SHARED_DGP),
        "module_a": asdict(MODULE_A),
        "module_b": asdict(MODULE_B),
        "calibration": asdict(CALIBRATION),
        "reporting": asdict(REPORTING),
    }
