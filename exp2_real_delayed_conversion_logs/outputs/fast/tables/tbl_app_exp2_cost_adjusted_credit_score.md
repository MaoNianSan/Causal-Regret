# Cost-normalization robustness check only. The transformed cost field is not interpreted as monetary profit or ROI.

|   Cost lambda | Route                           |   Cost-adjusted top-k score / 1,000 |   Cost-adjusted score difference vs arrival anchor / 1,000 |   Top-10 overlap vs arrival anchor |
|--------------:|:--------------------------------|------------------------------------:|-----------------------------------------------------------:|-----------------------------------:|
|           0.1 | Arrival-bin anchor (diagnostic) |                           270.671   |                                                     0      |                                  1 |
|           0.1 | First click or touch            |                            22.2161  |                                                  -248.455  |                                  0 |
|           0.1 | Last click or touch             |                            22.397   |                                                  -248.274  |                                  0 |
|           0.1 | Linear attribution              |                            20.6829  |                                                  -249.988  |                                  0 |
|           0.1 | Time-decay attribution          |                            20.8912  |                                                  -249.779  |                                  0 |
|           0.1 | EM soft attribution             |                            20.9576  |                                                  -249.713  |                                  0 |
|           0.5 | Arrival-bin anchor (diagnostic) |                           136.857   |                                                     0      |                                  1 |
|           0.5 | First click or touch            |                            -6.05117 |                                                  -142.908  |                                  0 |
|           0.5 | Last click or touch             |                            -9.37463 |                                                  -146.232  |                                  0 |
|           0.5 | Linear attribution              |                            -7.26503 |                                                  -144.122  |                                  0 |
|           0.5 | Time-decay attribution          |                            -9.3524  |                                                  -146.209  |                                  0 |
|           0.5 | EM soft attribution             |                            -9.3359  |                                                  -146.193  |                                  0 |
|           1   | Arrival-bin anchor (diagnostic) |                             9.46935 |                                                     0      |                                  1 |
|           1   | First click or touch            |                           -23.5523  |                                                   -33.0217 |                                  0 |
|           1   | Last click or touch             |                           -24.9056  |                                                   -34.375  |                                  0 |
|           1   | Linear attribution              |                           -24.7684  |                                                   -34.2378 |                                  0 |
|           1   | Time-decay attribution          |                           -24.8732  |                                                   -34.3425 |                                  0 |
|           1   | EM soft attribution             |                           -24.8719  |                                                   -34.3412 |                                  0 |
