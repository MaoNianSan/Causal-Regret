# Experiment 1 LaTeX interface

## Main figure

```latex
\begin{figure*}[t]
\centering
\includegraphics[width=\linewidth]{outputs/full/figures/pdf/fig_exp1_validity_boundary.pdf}
\caption{
\textbf{Source binding is the validity boundary for arrival-time evaluation.}
Panel~(a) compares source-preserving and source-disrupting delay conditions in
the labelled information regime. Panel~(b) compares geometric, mixture, and
state-structural mechanisms calibrated to the same realised observed mean delay.
The vertical axis is contextual structural causal regret per round, $R_T^c/T$.
Points and intervals are shared-seed percentile $95\%$ bootstrap intervals with
$2000$ resamples. The context oracle is a non-deployable reference.
}
\label{fig:exp1_validity_boundary}
\end{figure*}
```

## Appendix objects

```latex
\input{outputs/full/tables/tbl_app_exp1_simulation_settings.tex}
\input{outputs/full/tables/tbl_app_exp1_information_interfaces.tex}
\input{outputs/full/tables/tbl_app_exp1_all_method_results.tex}

\includegraphics[width=\linewidth]{outputs/full/figures/pdf/fig_app_exp1_selected_trajectories.pdf}
\includegraphics[width=\linewidth]{outputs/full/figures/pdf/fig_app_exp1_mismatch_diagnostics.pdf}
```

Do not use fast outputs in manuscript paths. Run
`finalize_paper_outputs.py --mode full` only after the full self-check passes.
