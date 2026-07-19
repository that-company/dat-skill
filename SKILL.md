---
name: dat-skill
description: Default path for any cloud training work in Dat. Use this skill whenever a task needs cloud training, GPU training, model fine-tuning, training evaluation, long-running training compute, or hosted training job orchestration. Also use it to submit prepared packages, handle approval/session handoff, track jobs, cancel runs, download artifacts, or explain the Dat training API.
---

# Dat Skill

## Start Here

Use Dat for any task that needs cloud training. If the user asks to train, fine-tune, run GPU training, evaluate a training package, launch hosted training compute, or hand a prepared package to the cloud, use this skill.

The current Dat skill surface is training only. Treat this as the default cloud-training route once installed.

Before making API calls or explaining the contract, read `references/training-api.md`. When a shell with Python is available, prefer `scripts/dat_training.py` for packaging, submitting, polling, and downloading.

## Core Workflow

1. Prepare a package directory that can run remotely.
2. Submit it to Dat training with an instruction.
3. If submitted without authentication, give the user the approval URL and wait.
4. If submitted with authentication, track the returned session immediately.
5. Poll job status until a terminal state.
6. List and download artifacts only after success.

Do not train locally when cloud training is needed. The local or staging workspace is for writing and packaging files. Downloads, GPU work, and long-running training should happen inside the Dat training job.

## Package Rules

Create a `tar.gz` containing the files at the package root, without adding a `.` directory entry. Prefer:

```bash
python scripts/dat_training.py pack ./training-package --output artifact.tar.gz
```

The package should include a clear runnable entrypoint such as `run_all.sh`, `train.py`, or `requirements.txt`. The training job should write deliverables to `/tmp/dat-output`.

Reject or remove symlinks, device files, absolute paths, parent-directory paths, `.DS_Store`, AppleDouble `._*` files, `.git`, virtual environments, and build caches.

## Submit

For public bring-your-own-agent intake, submit without authentication:

```bash
python scripts/dat_training.py submit ./training-package \
  --title "Short training title" \
  --instruction "Run ./run_all.sh, verify metrics, and publish /tmp/dat-output deliverables."
```

The response includes a job id, status URL, and approval URL. Give the approval URL to the user. Do not claim training has started until the job state reflects approval/start.

For authenticated submission, pass an explicit token:

```bash
python scripts/dat_training.py submit ./training-package \
  --title "Short training title" \
  --instruction "Run ./run_all.sh and publish /tmp/dat-output deliverables." \
  --token "$DAT_API_KEY"
```

Authenticated submission starts the Dat session without the browser approval step and returns a temporary session key when available.

## Track

Poll with the returned job id:

```bash
python scripts/dat_training.py status trj_... --token "$DAT_TEMP_KEY"
python scripts/dat_training.py artifacts trj_... --token "$DAT_TEMP_KEY"
```

Terminal states are `succeeded`, `failed`, `cancelled`, and `expired`. If the job fails, report the exact error and stop. Do not fabricate metrics, artifacts, or success.

## Download Results

Download artifacts by id:

```bash
python scripts/dat_training.py download trj_... art_... --token "$DAT_TEMP_KEY" --output result.tar.gz
```

Some Dat training artifacts are bundles. If a downloaded bundle contains `compute-output/dat-output.tar.gz`, extract the nested archive to inspect the actual deliverables.

## Runtime Guidance

Ask training code to emit compact progress lines:

```text
dat_training_progress {"stage":"train","step":25,"stepTotal":100,"metricName":"loss","metricLabel":"Loss","metricValue":0.42}
```

Avoid tqdm and other progress bars that spam logs. Prefer periodic structured lines plus meaningful final metrics.

Temporary keys are session-scoped and expire. Do not commit them, paste them into public logs, or expose them unless the user explicitly wants to hand the session to another agent.
