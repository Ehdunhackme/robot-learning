# SO-101 path learning

The simulator runs three SO-101 tasks in MuJoCo. Obstacle reach and shelf inspection use trained path scorers. Puck push chooses a paddle stroke from similar training layouts. Choose a controller and scrub the replay to see where strategies diverge. Settings include layout adjustments, planned paths, camera angles and measurements.

![SO-101 pushing a blue puck across a raised work surface](media/simulator.png)

[Watch the obstacle reach comparison](web/demo.mp4) · [Watch the puck comparison](web/puck.mp4) · [Watch the shelf comparison](web/shelf.mp4) · [Shelf study](SHELF_STUDY.md) · [Obstacle reach results](RESULTS.md) · [Run autoresearch](program.md)

[Run the interactive article locally](article/README.md). It includes the video player, 3D viewer, interactive training curve and per-run data.

## Start with these replays

In **Puck push**, both controllers get the same 60 mm opening layout. The learned stroke finishes 14.62 mm from the target center and the straight stroke finishes 9.50 mm away. Success requires the jaws to hold the paddle throughout puck contact, a clean stroke, a final error of at most 10 mm and a final puck speed below 5 mm/s. Choose **Release paddle** to see what happens when the arm opens its jaws.

In **Shelf inspection**, open **Settings and run details** and select **Inspect closest pass** to see the jaw pass the roof by 0.75 mm. Two further examples show where the learned and fixed routes win. In **Obstacle reach**, select **Fixture** in settings to switch between the fence, post and overhead zone.

On the narrowest tested opening, 90 mm, the original library offered a geometrically clear inward route in 3 of 96 layouts. With six additional shelf-entry routes, the fixed and learned methods each completed 74 of the 96 full inspections. [Per-layout results](experiments/shelf/episodes.json)

## Open the studio

On Windows with Python 3.13 installed, double-click **Start SO-101.cmd**. The launcher creates a virtual environment and installs the simulator dependencies on first use. The viewer and released models run on a CPU. Drag to orbit, scroll to zoom, or drag the timeline to inspect an individual pose. **New layout** samples another scene. **Apply layout** reruns the controllers after a change. Planned paths can be enabled for the reach and shelf tasks.

On Linux or macOS, from the project root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 .venv/bin/python studio.py --open
```

The default URL is http://127.0.0.1:8766/. The browser uses WebGL 2 and the included Three.js modules and geometry. Each task has a standalone recorded comparison.

## Puck push study

[Robot path learning with an SO-101 arm](https://dunlichan.com/writings/so101-path-learning/) includes the path-learning simulator, measured training curve, paddle comparison and surface-transfer test. To reproduce the transfer test on the original 64 layouts, run `python puck_transfer.py --workers 6`. It keeps both controllers frozen, checks each nominal outcome against the original trials and writes [the per-run results](experiments/puck/transfer.json).

In the original wrist-mounted paddle experiment, the controller learns which of seven lateral paddle offsets to use from the outcomes of 192 simulated training layouts. It estimates the cost of each action using nearby layouts in starting position, push direction and distance. Validation on 48 separate layouts selected three neighbors. On 64 held-out layouts, the learned push succeeded 45 times with 12.0 mm mean endpoint error. The straight push succeeded 18 times with 20.1 mm mean error. Validation selected the straight push as the best constant action. These figures describe one simulated puck, paddle, friction setting and split. [Model](experiments/puck/push.json) · [Episode data](experiments/puck/episodes.json)

The live puck demo starts with an independent paddle between two jaw pads. MuJoCo integrates the free body through contact and gravity. Select **Gripper view** to inspect the contact or **Release paddle** to open the fingers. The original stroke selector scored 21/64 with the hand-held paddle and straight strokes scored 7/64 on the same layouts. Run `python puck_grasp_transfer.py` to reproduce the paired results and the open-jaw control. [Hand-held paddle trials](experiments/puck/grasp-transfer.json)

Reproduce the CPU study with `python puck_study.py --workers 8`. With the studio running, `python record_puck.py` records synchronized browser frames using Playwright, Pillow and ffmpeg. The task selection and visible success condition draw on how ManiSkill presents manipulation tasks and how robosuite defines environment goals. [ManiSkill task gallery](https://maniskill.readthedocs.io/en/latest/tasks/table_top_gripper/index.html) · [robosuite environments](https://robosuite.ai/docs/modules/environments.html)

## Single-fixture model

We trained on 4,096 procedurally generated scenes. The training labels come from checking the official SO-101 model for contact along each candidate trajectory. The selected neural network estimates collision risk for each path. Inference combines that risk with additional joint travel to rank the candidates. The UI selects the path before running the servo simulator. A direct baseline interpolates between the same two joint poses.

The learned model reached **87/96** targets in held-out servo replays. Direct interpolation reached **18/96**. These tasks cover one known box-shaped fixture, a known scene state, reachable joint-pose targets and one training seed. The arm has six actuators. The benchmark keeps the gripper opening fixed throughout each reach and provides wrist-roll endpoint poses. The results measure simulated reaching.

## Single-fixture dataset, training and experiment loop

`prepare.py` creates the fixed train, validation and test splits using MuJoCo 3.3.7. The release includes the resulting data, training source snapshots and all six models. The official autoresearch repository is installed as a separate checkout on the development machine and the A100. Its upstream GPU environment is separate from the arm training environment. Cloning the project elsewhere requires fetching that checkout to inspect or run the original language-model workload.

```bash
git clone https://github.com/karpathy/autoresearch.git tools/autoresearch
git -C tools/autoresearch checkout 228791fb499afffb54b46200aca536f79142f117
```

For the arm experiments, use a CUDA-capable PyTorch install. The qualified A100 runtime used Python 3.10, PyTorch 2.7.0 and MuJoCo 3.3.7. With that PyTorch available in the arm environment, run the following from the project directory.

```bash
.venv/bin/python check_contacts.py
OPENBLAS_NUM_THREADS=1 .venv/bin/python train.py new-trial --recipe shared --width 96 --depth 2
```

Follow [the arm-specific experiment brief](program.md) to propose and test code changes. The trainer writes to a fresh trial folder and appends a keep/discard decision. The fixed work budget is 1,000 optimizer updates per trial. Training, evaluation, and web serving can be run independently. The complete release already contains the fixed dataset and frozen final scores. Generating new data with `python prepare.py --workers 8` replaces the generated data files in that checkout.

## Model and viewer assets

The SO-101 follower MJCF and 13 STL files are from TheRobotStudio at commit `141aea7bcac2744d92998e30268c413202a56f96`. Their Apache 2.0 license is in [assets/so101/LICENSE](assets/so101/LICENSE). MuJoCo uses the original mesh files. `export_mesh.py` clusters visual vertices at 0.60 mm for faster browser rendering. The viewer vendors Three.js r180 under its [MIT license](web/vendor/LICENSE). [SO-101 simulation source](https://github.com/TheRobotStudio/SO-ARM100/tree/141aea7bcac2744d92998e30268c413202a56f96/Simulation/SO101) · [Karpathy autoresearch](https://github.com/karpathy/autoresearch)

The desktop UI checks use Python Playwright and Chromium. With the studio running, `python check_studio.py` exercises playback, both planners, target and fixture edits, scene generation and mobile layout. The shelf tests also exercise the cutaway, camera, surface readout, curated comparisons and adjustable opening. `python record_demo.py` renders the comparison using MuJoCo, Pillow and ffmpeg. Run `python record_shelf.py` to render the shelf film with those same dependencies.
