# Attribution route definitions and information interfaces.

| route                   | information_interface   | reference_role          | diagnostic_only   | deployable   | assignment_rule                                                 | method_display_name              |
|:------------------------|:------------------------|:------------------------|:------------------|:-------------|:----------------------------------------------------------------|:---------------------------------|
| arrival_bin_anchor      | arrival_bin             | diagnostic_control      | True              | False        | constructed arrival-bin modal campaign-source-day anchor        | Arrival-bin anchor (diagnostic)  |
| arrival_time_naive      | arrival_time            | diagnostic_control      | True              | False        | constructed arrival-bin modal campaign-source-day anchor        | Arrival-bin anchor (diagnostic)  |
| first_click             | source_candidate        | none                    | False             | True         | first clicked source cell; first source event if no click       | First click or touch             |
| last_click              | source_candidate        | none                    | False             | True         | last clicked source cell; last source event if no click         | Last click or touch              |
| linear_attribution      | source_candidate        | none                    | False             | True         | equal credit across unique candidate source-time decision cells | Linear attribution               |
| time_decay_soft         | source_candidate        | none                    | False             | True         | credit proportional to exponential recency weight               | Time-decay attribution           |
| soft_attribution_em     | source_candidate        | diagnostic_control      | True              | False        | EM-style exposure-calibrated responsibility allocator           | EM soft attribution              |
| last_touch              | source_candidate        | none                    | False             | True         | most recent candidate source event                              | Last touch                       |
| uniform_soft            | source_candidate        | none                    | False             | True         | equal credit across candidate source-event rows                 | Uniform soft attribution         |
| click_prior_soft        | source_candidate        | none                    | False             | True         | recency weight multiplied by click prior                        | Click prior soft attribution     |
| source_linked_reference | source_labelled         | source_linked_reference | False             | False        | single Criteo-attributed candidate source cell; audit only      | Criteo-attributed cell reference |
