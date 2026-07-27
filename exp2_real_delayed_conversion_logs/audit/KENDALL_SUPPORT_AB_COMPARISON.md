# Kendall Support A/B Comparison

Variant A is the implementation used by the existing full run. Variant B changes only Kendall support selection and holds each comparison's full-sample union-positive cell IDs fixed across all UID-cluster replicates.

| comparison | variant | bootstrap_support_min | bootstrap_support_mean | bootstrap_support_max | bootstrap_tau_mean | bootstrap_tau_median | bootstrap_tau_ci_lower | bootstrap_tau_ci_upper | point_inside_ci | fraction_nan_tau | runtime_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_touch vs arrival_bin_anchor | A_current_replicate_support | 2898 | 2967.201000 | 3042 | 0.055645 | 0.055703 | 0.032275 | 0.079690 | False | 0.000000 | 1.405183 |
| first_touch vs arrival_bin_anchor | B_frozen_full_sample_support | 3866 | 3866.000000 | 3866 | 0.121508 | 0.121340 | 0.100439 | 0.141590 | True | 0.000000 | 1.425566 |
| last_touch vs arrival_bin_anchor | A_current_replicate_support | 2335 | 2400.685000 | 2464 | 0.215647 | 0.215743 | 0.192386 | 0.240746 | False | 0.000000 | 1.188759 |
| last_touch vs arrival_bin_anchor | B_frozen_full_sample_support | 3118 | 3118.000000 | 3118 | 0.257814 | 0.257772 | 0.237610 | 0.278193 | True | 0.000000 | 1.261918 |
| linear_credit vs arrival_bin_anchor | A_current_replicate_support | 3964 | 4077.093000 | 4228 | 0.170570 | 0.170609 | 0.150741 | 0.190727 | False | 0.000000 | 1.413899 |
| linear_credit vs arrival_bin_anchor | B_frozen_full_sample_support | 5206 | 5206.000000 | 5206 | 0.198295 | 0.198074 | 0.181934 | 0.214593 | True | 0.000000 | 1.596799 |
| time_decay_credit vs arrival_bin_anchor | A_current_replicate_support | 3964 | 4077.093000 | 4228 | 0.202380 | 0.202234 | 0.182207 | 0.222255 | False | 0.000000 | 1.402666 |
| time_decay_credit vs arrival_bin_anchor | B_frozen_full_sample_support | 5206 | 5206.000000 | 5206 | 0.220830 | 0.220602 | 0.203968 | 0.237227 | True | 0.000000 | 1.526515 |
| first_touch vs last_touch | A_current_replicate_support | 3124 | 3194.951000 | 3281 | 0.266601 | 0.266831 | 0.244511 | 0.289307 | False | 0.000000 | 1.503725 |
| first_touch vs last_touch | B_frozen_full_sample_support | 4177 | 4177.000000 | 4177 | 0.429220 | 0.429631 | 0.407450 | 0.450254 | False | 0.000000 | 1.658743 |
| first_touch vs linear_credit | A_current_replicate_support | 3848 | 3966.369000 | 4117 | 0.583000 | 0.583153 | 0.568033 | 0.597146 | False | 0.000000 | 1.667158 |
| first_touch vs linear_credit | B_frozen_full_sample_support | 5106 | 5106.000000 | 5106 | 0.667916 | 0.668171 | 0.653096 | 0.681379 | False | 0.000000 | 1.816719 |
| first_touch vs time_decay_credit | A_current_replicate_support | 3848 | 3966.369000 | 4117 | 0.398825 | 0.398789 | 0.381696 | 0.415307 | False | 0.000000 | 1.666675 |
| first_touch vs time_decay_credit | B_frozen_full_sample_support | 5106 | 5106.000000 | 5106 | 0.545770 | 0.546096 | 0.526900 | 0.563526 | False | 0.000000 | 1.796112 |
| last_touch vs linear_credit | A_current_replicate_support | 3848 | 3966.369000 | 4117 | 0.601668 | 0.601529 | 0.588182 | 0.615079 | False | 0.000000 | 1.620523 |
| last_touch vs linear_credit | B_frozen_full_sample_support | 5106 | 5106.000000 | 5106 | 0.650887 | 0.650834 | 0.638452 | 0.662739 | False | 0.000000 | 1.721251 |
| last_touch vs time_decay_credit | A_current_replicate_support | 3848 | 3966.369000 | 4117 | 0.820789 | 0.820765 | 0.813188 | 0.828199 | False | 0.000000 | 1.510316 |
| last_touch vs time_decay_credit | B_frozen_full_sample_support | 5106 | 5106.000000 | 5106 | 0.798260 | 0.798170 | 0.792039 | 0.804262 | False | 0.000000 | 1.636335 |
| linear_credit vs time_decay_credit | A_current_replicate_support | 3848 | 3966.369000 | 4117 | 0.673399 | 0.673171 | 0.661320 | 0.685509 | False | 0.000000 | 1.666030 |
| linear_credit vs time_decay_credit | B_frozen_full_sample_support | 5106 | 5106.000000 | 5106 | 0.792565 | 0.792626 | 0.780809 | 0.804504 | False | 0.000000 | 1.847693 |

Variant B leaves the full-sample point estimates, allocation-TV calculations, Top-k calculations, UID draws, score vectors, and interval method unchanged. Its support minimum and maximum equal the full-sample support for every comparison.
