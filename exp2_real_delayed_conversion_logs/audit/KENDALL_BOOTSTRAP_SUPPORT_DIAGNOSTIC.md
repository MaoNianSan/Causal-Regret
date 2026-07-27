# Kendall Bootstrap Support Diagnostic

Source run: `exp2-full-20260726T235202+0800`. The formal output directory was read only.

Variant A exactly reproduced all saved support counts and Kendall tau-b draws. Every comparison has replicate support below and varying around a mean far below its full-sample support.

| comparison | full_sample_support_count | bootstrap_support_min | bootstrap_support_mean | bootstrap_support_max | point_estimate_tau | bootstrap_tau_mean | bootstrap_tau_ci_lower | bootstrap_tau_ci_upper | point_inside_ci | fraction_nan_tau |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| first_touch vs arrival_bin_anchor | 3866 | 2898 | 2967.201000 | 3042 | 0.115596 | 0.055645 | 0.032275 | 0.079690 | False | 0.000000 |
| last_touch vs arrival_bin_anchor | 3118 | 2335 | 2400.685000 | 2464 | 0.261370 | 0.215647 | 0.192386 | 0.240746 | False | 0.000000 |
| linear_credit vs arrival_bin_anchor | 5206 | 3964 | 4077.093000 | 4228 | 0.204823 | 0.170570 | 0.150741 | 0.190727 | False | 0.000000 |
| time_decay_credit vs arrival_bin_anchor | 5206 | 3964 | 4077.093000 | 4228 | 0.230445 | 0.202380 | 0.182207 | 0.222255 | False | 0.000000 |
| first_touch vs last_touch | 4177 | 3124 | 3194.951000 | 3281 | 0.298453 | 0.266601 | 0.244511 | 0.289307 | False | 0.000000 |
| first_touch vs linear_credit | 5106 | 3848 | 3966.369000 | 4117 | 0.604426 | 0.583000 | 0.568033 | 0.597146 | False | 0.000000 |
| first_touch vs time_decay_credit | 5106 | 3848 | 3966.369000 | 4117 | 0.419742 | 0.398825 | 0.381696 | 0.415307 | False | 0.000000 |
| last_touch vs linear_credit | 5106 | 3848 | 3966.369000 | 4117 | 0.623890 | 0.601668 | 0.588182 | 0.615079 | False | 0.000000 |
| last_touch vs time_decay_credit | 5106 | 3848 | 3966.369000 | 4117 | 0.834000 | 0.820789 | 0.813188 | 0.828199 | False | 0.000000 |
| linear_credit vs time_decay_credit | 5106 | 3848 | 3966.369000 | 4117 | 0.686301 | 0.673399 | 0.661320 | 0.685509 | False | 0.000000 |

No comparison produced a NaN, constant vector, or zero-mass vector in the 1,000 formal replicates. Point and replicate score construction both use credits divided by the same eligible-impression denominator on the same cell universe; the observed mismatch is support selection, not score normalization.
