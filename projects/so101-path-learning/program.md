# Autoresearch for SO-101 motion planning

Use this file as the experiment brief for a coding agent in this repository. Karpathy's original workflow is installed under `tools/autoresearch` at commit `228791fb499afffb54b46200aca536f79142f117`. This adaptation trains a robot path selector on a single GPU.

## Shelf experiment

The five-panel inspection task has a separate frozen dataset, ranker and study report. The starting result is 81/96, 73/96 and 74/96 successful servo tasks at 180, 125 and 90 mm. Read [the shelf study](SHELF_STUDY.md) and inspect [the selection record](experiments/shelf/selection.json) before planning new experiments. The shipped test seeds have already been evaluated.

For a new shelf trial, branch into a separate checkout to preserve the released weights. Propose a change to candidate features or scoring and change one factor at a time. Reuse the 1,600 training scenes, 240 validation scenes, seed 7231 and 1,100 optimizer updates. Run `python shelf_study.py train` in the arm CUDA environment. Compare validation cost and clear counts to the incumbent. If features change, regenerate features from the same scene settings. Select by validation, then freeze and test on fresh seeds. Keep the validation-best fixed route in the servo comparison.

## Single-fixture objective

Minimize the fixed validation cost on 640 scenes. Any sampled contact costs 1. A clear path costs 0.12 times its extra joint travel relative to direct interpolation, capped at 0.45. Also inspect the clear rate and travel separately. Lower cost can reflect shorter paths even when the clear rate falls. The model chooses one of 13 paths given the start and goal joint poses and a fixture box.

## Run an experiment

1. Work from the project root in a fresh local Git branch. Read the latest valid row in `experiments/results.tsv` and the incumbent in `experiments/champion.json`. Review its model and validation score.
2. Propose one testable change to `train.py`, `policy.py`, or `kinematics.py`. Record the hypothesis. Preserve the NumPy inference interface used by the viewer.
3. Keep the 4,096 training scenes, validation split, training seed, 1,000 optimizer updates and batch size 256 fixed for this comparison. Time and record each trial. Architectures can take different wall times. Fix research inputs in `prepare.py` and `arm.py`. The available inputs are robot joint poses, known fixture pose and size, and forward kinematics computed from them.
4. Evaluate a candidate using a fresh tag. On the A100, for example, run `OPENBLAS_NUM_THREADS=1 .venv/bin/python train.py trial-007 --recipe shared --width 96 --depth 2`. If implementing a new recipe, add its CLI choice and inference/export path. A candidate can be proposed and executed by the agent operating this repository. Running that command alone performs one training trial.
5. The trainer saves the weights, editable source snapshots, score and accelerator under `experiments/<tag>`. It promotes a candidate on strictly lower validation cost. Preserve rejected trials. For a crash, preserve the error and use a fresh tag for the corrected attempt. Restore the incumbent source from its snapshots in a fresh branch if needed.
6. Repeat for the agreed trial budget and report all trials, tradeoffs and the incumbent. The move from the first model to the published one used six trials. No API key is used by the trainer itself.

## Evaluation

The released test set has already been scored. Keep it out of model development. For a new confirmatory study, declare and freeze a fresh split before collecting any results for it. Choose the model using validation, then run `final_score.py` once on that study's test split. It compares direct interpolation, the best fixed detour by validation cost, a sparse geometry rule, the initial model, the selected model and a privileged oracle over the 13 candidates. It separately executes direct and learned paths under MuJoCo servo dynamics on the first 96 test scenes.

The initial results use one optimization seed. Include independent training seeds before drawing conclusions about run-to-run effects. New physical-arm experiments require their own calibration, control and evaluation setup.
