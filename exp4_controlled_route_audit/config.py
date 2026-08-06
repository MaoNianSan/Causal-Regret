"""Compatibility exports for the Exp4 v2 configuration package."""

from pathlib import Path

from exp4.configuration.parameters import CALIBRATION, MODULE_A, MODULE_B, REPORTING, SHARED_DGP
from exp4.configuration.registries import (
    AUDIT_DESIGN_ORDER,
    AUDIT_DESIGN_REGISTRY,
    CONTROL_ORDER,
    CONTROL_REGISTRY,
    ROUTE_ORDER,
    ROUTE_REGISTRY,
)
from exp4.configuration.run_modes import mode_settings
from exp4.configuration.schema import *
from exp4.outputs.writers import config_hash, frozen_config_payload

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_ROOT = BASE_DIR / "outputs" / "runs"

PARAMETERS = SHARED_DGP
MODULE_A_ROUTE_LABEL_RATES = MODULE_A.route_label_rates
MODULE_A_ATTRIBUTION_PROXY_NOISE_SDS = MODULE_A.proxy_noise_sds
AUDIT_EVIDENCE_RATES = MODULE_B.audit_evidence_rates
PRIMARY_FIGURE_STEMS = [MAIN_FIGURE_ID]
APPENDIX_FIGURE_STEMS = list(APPENDIX_FIGURE_IDS)
