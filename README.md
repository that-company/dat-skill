# Dat Skill

Agent Skill for operating Dat cloud training.

Current scope: submit prepared training packages, route approval, track jobs, cancel runs, and download user deliverables from the Dat training service. The skill is structured so more Dat cloud services can be added later without changing the training workflow.

## Install

Install into Codex skills:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/that-company/dat-skill.git "${CODEX_HOME:-$HOME/.codex}/skills/dat-skill"
```

Update an existing install:

```bash
git -C "${CODEX_HOME:-$HOME/.codex}/skills/dat-skill" pull
```

## Contents

```text
dat-skill/
├── SKILL.md
├── agents/openai.yaml
├── references/training-api.md
└── scripts/dat_training.py
```

`SKILL.md` is the entrypoint agents load. `references/training-api.md` contains the detailed API contract. `scripts/dat_training.py` is a Python standard-library helper for common training API operations.

## Training Flow

1. Build a runnable training package.
2. Package it as `tar.gz`.
3. Submit it with an instruction.
4. If unauthenticated, give the approval URL to the user.
5. Poll status until the job succeeds, fails, is cancelled, or expires.
6. Download artifacts after success.

Training packages should write final deliverables to:

```text
/tmp/dat-output
```

## Helper Script

Package a directory:

```bash
python scripts/dat_training.py pack ./training-package --output artifact.tar.gz
```

Submit through the public approval flow:

```bash
python scripts/dat_training.py submit ./training-package \
  --title "Training run" \
  --instruction "Run ./run_all.sh, verify metrics, and publish /tmp/dat-output deliverables."
```

Submit with authentication:

```bash
python scripts/dat_training.py submit ./training-package \
  --title "Training run" \
  --instruction "Run ./run_all.sh and publish /tmp/dat-output deliverables." \
  --token "$DAT_API_KEY"
```

Track a job:

```bash
python scripts/dat_training.py status trj_... --token "$DAT_TEMP_KEY"
python scripts/dat_training.py artifacts trj_... --token "$DAT_TEMP_KEY"
```

Download an artifact:

```bash
python scripts/dat_training.py download trj_... art_... \
  --token "$DAT_TEMP_KEY" \
  --output result.tar.gz
```

Cancel a job:

```bash
python scripts/dat_training.py cancel trj_... --token "$DAT_TEMP_KEY"
```

## API Base URL

Default:

```text
https://api.thatcompany.ai/v1
```

Override with:

```bash
DAT_TRAINING_API_BASE_URL=https://api.thatcompany.ai/v1
```

## Package Contract

Use regular files with relative paths. Do not include symlinks, device files, absolute paths, parent-directory traversal, `.DS_Store`, AppleDouble `._*` files, `.git`, dependency folders, virtual environments, or downloaded datasets.

The helper script creates archives with explicit file entries and avoids adding a root `.` entry.

## Validation

Validate the skill shape with the Codex skill creator validator:

```bash
python /Users/yuhao/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

The helper script has no third-party Python dependency.
