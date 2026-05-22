# Contributing

## Development Setup

1. Create and activate venv:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure local environment:

```bash
cp .env.example .env
```

## Run Locally

```bash
make run
```

## Before Opening a PR

Run public/safety checks:

```bash
make check
```

Then review what you are committing:

```bash
git diff
git diff --cached
```

## Pull Request Notes

- Keep PRs focused and small.
- Include a short test plan.
- Document any new environment variables.
