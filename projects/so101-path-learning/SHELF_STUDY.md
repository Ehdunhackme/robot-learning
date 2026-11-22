# How narrow a shelf can the SO-101 inspect?

Arcbench gives the arm a target inside a five-panel shelf. It starts to one side, enters the opening, holds its tool within 8 mm of the target for 0.4 seconds, and returns to within 8 mm of home. Any modeled arm collision ends the run. In the featured 110 mm opening, direct joint interpolation clips the right wall at 2.296 s. The selected path clears the roof by a sampled 0.75 mm and completes the task at 7.608 s. The validation-selected fixed route makes the same motion on that scene. [Watch the synchronized replay](web/shelf.mp4)

## What we took from the research

| Question | Evidence | Decision in Arcbench |
|---|---|---|
| How do we show that a task actually got harder? | Chamzas and colleagues procedurally generate manipulation problems and compare planners on common datasets spanning five robots and eight environments. [MotionBenchMaker](https://arxiv.org/abs/2112.06402) | Reuse the same 96 start poses, targets and inspection depths at three shelf widths. Count how often each route library contains a clear way in. This isolates the effect of narrowing the opening on these scenes. |
| What makes a scene worth watching? | Neural MP demonstrates insertion into bins, shelves and cabinets and shows the effect of objects held in the gripper. Reaching inside gives the environment a visible purpose and exposes potential collisions along the arm. [Neural MP, examples and method](https://neuralmotionplanner.github.io/) | Place the target up to 105 mm behind the front face. Give the gripper time to settle there, then require the arm to come back out. A transparent roof and side panel expose the jaw throughout insertion. |
| What should a result measure? | Motion Policy Networks evaluates motion generation in clutter with goals that include reaching reliably and producing smooth motion. The authors also study depth observations and transfer to physical hardware. [Fishman et al.](https://proceedings.mlr.press/v205/fishman23a.html) | Score full servo execution separately from collision checks on sampled planned poses. Show actual tool travel, home error, collision and time. Our scope is a known shelf and known robot state in simulation. |
| How can a viewer locate the failure? | MoveIt visualizes physical contact locations in the planning scene. [MoveIt collision visualization](https://moveit.picknik.ai/main/doc/examples/visualizing_collisions/visualizing_collisions_tutorial.html) | Mark the first contact in 3D. For a successful pass, show the two closest points on the simulated arm and shelf. The timeline links the measured gap back to the exact displayed pose. |
| How should two nearly identical motions be compared? | Gleicher describes juxtaposition and superposition as complementary comparison designs and discusses the role of alignment. [Considerations for Visualizing Comparison](https://graphics.cs.wisc.edu/Papers/2018/Gle18/viscomp.pdf) | Use the same camera, scene and clock for both arms in the film. Freeze the direct arm at impact. In the interactive viewer, overlay the commanded paths on a single workcell. Label the final close-ups with each run's own timestamp. |

## Experiment

The environment varies starting joints, target height and reach, shelf height, lateral misalignment, opening width and insertion depth. Width ranges from 85 to 190 mm and depth from 45 to 105 mm. The published test changes width while holding the other properties of a given layout constant. The 13 original candidates interpolate between the starting and target joint poses with mid-course offsets. Six new candidates fold the arm, rotate toward the shelf, align just outside the mouth and insert. They vary the fold and retreat before alignment.

For each candidate, the model receives joint poses, geometry, candidate identity, sampled approximate link clearances and joint travel. It learns to estimate collision risk from an 81-pose inward collision check. The ranker balances that risk against extra joint travel. A successful simulated inspection requires the actuators to follow the entire inward, hold and outward command. The solver checks for contact every 2 ms. The detailed replay samples gripper positions and arm-to-shelf distances every 24 ms and on termination. Its displayed minimum is the smallest recorded shelf gap. Its precision refers to this simulated model.

Training used 1,600 scenes and validation used 240, each with its own seed and a random opening. Two networks with hidden widths 48 and 96 trained for 1,100 updates apiece on one NVIDIA A100 40 GB, with the same optimization seed and training budget. The width-48 network won on validation cost, 0.41895 versus 0.42268. The best single fixed route on the same validation objective was route 15. The test contains 96 new layout seeds, each evaluated at three widths. These are 288 cases and 864 method–case comparisons. Methods that select the same route share its deterministic execution, giving 688 distinct servo runs. [Selection record](experiments/shelf/selection.json) · [Episode scores](experiments/shelf/episodes.json)

| Opening | Original 13 contained a clear inward route | Expanded 19 contained a clear inward route | Direct completed | Fixed route completed | Learned completed |
|---|---:|---:|---:|---:|---:|
| 180 mm | 60/96 | 84/96 | 0/96 | 75/96 | 81/96 |
| 125 mm | 19/96 | 75/96 | 0/96 | 75/96 | 73/96 |
| 90 mm | 3/96 | 74/96 | 0/96 | 74/96 | 74/96 |

Narrowing the shelf from 180 to 90 mm reduced the number of layouts with a geometrically clear original route from 60 to 3. At 90 mm, the fixed and learned planners succeeded on precisely the same 74 layouts. At 180 mm, the learned selector rescued nine fixed-route failures and introduced three. Across all openings its advantage was 4/288, or 1.4 percentage points. A paired bootstrap over the 96 layout seeds gives a descriptive 95% interval from −1.0 to +3.8 points (20,000 resamples, RNG seed 9374, all three widths kept together). The evidence favors adding shelf-entry motions. A general gain from the learned selector remains uncertain.

## Three replays to try

- **Roof clearance** uses seed 720001, a 110 mm opening and 75 mm depth. Click **Closest pass**. The moving jaw comes closest to the roof at 3.048 s. The cutaway changes visibility only.
- **Learned route succeeds** uses held-out seed 610002, 180 mm and 102 mm. The fixed route makes contact at 2.930 s. Learning picks a different candidate and completes the inspection.
- **Fixed route succeeds** uses held-out seed 610014, 125 mm and 97 mm. The learned choice makes contact at 1.936 s. The fixed route completes the same task. These two examples were selected after testing to explain the difference between the methods.

## Reproduce and extend

The released weights, datasets, configuration, scores and episode-level decisions are included. The CPU studio can replay arbitrary seeds. To regenerate the study from scratch in a separate checkout with CUDA-enabled PyTorch, install the main requirements and run `OPENBLAS_NUM_THREADS=1 .venv/bin/python shelf_study.py all --workers 12`. Use the individual stages `generate`, `train` and `evaluate` to rerun part of the pipeline. The CPU-only `report` stage reconstructs the table and paired interval from the episode records. The nominal shelf pose is exact, the gripper opening stays fixed, and the inspection means holding a simulated tool point at a target. The study uses one training seed.

A strong follow-up would test how shelf-pose uncertainty changes the ranking. Freeze the planner's nominal shelf estimate, apply a reproducible translation or yaw error only to the execution fixture, and run the same trajectories again. Compare a travel-focused ranker to a clearance-focused one using paired successes, surface contacts and tool travel. Declare fresh layout seeds before model selection and repeat optimization with several seeds. That directly tests whether a submillimeter pass survives modest errors in the modeled shelf pose.
