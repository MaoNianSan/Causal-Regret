# Logged route sensitivity on the all-conversion cohort. Intervals are UID-cluster bootstrap intervals for allocation and ranking summaries, not causal-policy intervals.

| Route                           |   Top-k credited mass / 1,000 |   Allocation TV vs arrival anchor |   TV CI low |   TV CI high |   Top-10 overlap vs arrival anchor |   Overlap CI low |   Overlap CI high |
|:--------------------------------|------------------------------:|----------------------------------:|------------:|-------------:|-----------------------------------:|-----------------:|------------------:|
| Arrival-bin anchor (diagnostic) |                      377.816  |                          0        |    0        |     0        |                                  1 |                1 |                 1 |
| First click or touch            |                       42.6443 |                          0.924371 |    0.922834 |     0.926007 |                                  0 |                0 |                 0 |
| Last click or touch             |                       40.689  |                          0.922243 |    0.920797 |     0.923665 |                                  0 |                0 |                 0 |
| Linear attribution              |                       39.7536 |                          0.923484 |    0.922018 |     0.924933 |                                  0 |                0 |                 0 |
| Time-decay attribution          |                       40.6902 |                          0.922515 |    0.921111 |     0.923908 |                                  0 |                0 |                 0 |
