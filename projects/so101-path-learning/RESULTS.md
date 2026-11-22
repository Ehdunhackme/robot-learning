# Does learning a detour help the SO-101 reach around fixtures?

For the five-panel shelf, the width sweep and the stronger fixed-route comparison, read [the shelf study](SHELF_STUDY.md).

Across 800 held-out scenes, the selected model produced **723 clear paths (90.4%)**. Direct joint interpolation produced **127 (15.9%)**. A fixed detour selected on validation was a much stronger baseline. It produced **715 (89.4%)**, with greater mean joint travel.

| Method | Clear plans out of 800 | Mean joint travel | Mean cost |
|---|---:|---:|---:|
| Direct interpolation | 127 | 1.785 rad | 0.8413 |
| Fixed detour selected on validation | 715 | 3.393 rad | 0.2047 |
| Sparse geometry rule | 554 | 2.297 rad | 0.3299 |
| First learned model | 716 | 3.022 rad | 0.1787 |
| Selected learned model | 723 | 2.504 rad | 0.1368 |
| Oracle over all 13 candidates | 730 | 2.307 rad | 0.1237 |

The selected model reduced mean joint travel by **17.1%** relative to the first learned model while clearing seven more scenes. Cost fell by 0.0419. A paired bootstrap over held-out scenes gave a 95% interval of 0.0316 to 0.0520 for the cost reduction. The interval measures scene variability for these trained weights. Independent training seeds would be needed to estimate training variability. Travel measures the sum of joint-space step lengths along the full commanded path, including commands for paths that would make contact.

## Physical simulation replay

We executed the first 96 test scenes in their original order under MuJoCo position-servo dynamics. Both methods received the same endpoints and fixture. A run stops on modeled contact or on settling within 8 mm of the target after the commanded move.

| Policy | Reached | Contact | Missed the final tolerance |
|---|---:|---:|---:|
| Direct interpolation | 18 | 78 | 0 |
| Selected model | 87 | 9 | 0 |

The studio shows the same execution code. Its three default examples come from a separate demonstration seed range and were deliberately chosen to show a direct-path contact that the learned policy avoids. New scenes can expose failures. [Watch the side-by-side servo executions](web/demo.mp4).

## Autoresearch results

All models used the same 4,096 training scenes, 640 validation scenes, optimization seed, batch size 256 and 1,000 gradient updates on one 40 GB A100. Each trial compares against the best previous validation cost. The final test was scored after model selection.

| Trial | Hypothesis | Validation cost | Decision |
|---|---|---:|---|
| baseline | Predict observed path cost from the joint poses and box | 0.1779 | Keep |
| capacity | Increase the network width and add a layer | 0.1762 | Keep |
| relative | Describe the obstacle relative to the arm's sweep | 0.1608 | Keep |
| link-clearance | Add five sparse forward-kinematic clearance estimates per path | 0.1605 | Keep |
| contact-loss | Penalize optimistic contact predictions more heavily | 0.1606 | Discard |
| shared-risk | Share one collision-risk model across candidates and compute joint travel explicitly | 0.1421 | Keep |

The benchmark cost is 1 for any sampled contact. For a clear path it is 0.12 times the extra joint travel relative to direct interpolation, capped at 0.45. This makes a successful short route preferable to a successful long one. The sparse geometry rule uses only approximate link centerlines at five interior poses and chooses the shortest apparently clear path. The oracle uses the evaluation labels.

## Scope

The model selects among 13 parametric joint-space paths for one box, a fixed gripper opening and known start and target joint poses. Fixtures include low fences, tall posts and overhead keep-out zones. Some scenes have no clear candidate. The geometric score checks 81 poses per path. Contact between samples can be missed. The servo check uses the upstream actuator model and MuJoCo contacts at 2 ms simulation steps. The experiments cover simulation and one training seed.

[Full metrics and dataset hashes](experiments/final.json) · [Per-scene model choices](experiments/decisions.npz) · [Per-scene servo outcomes](experiments/servo.json) · [Trial history](experiments/results.tsv)
