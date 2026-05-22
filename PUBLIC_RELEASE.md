# Public Release Checklist

Use this checklist before publishing changes.

## 1) Secrets Safety

- Keep local credentials only in .env.
- Ensure .env is never committed.
- Keep placeholders only in .env.example.
- Rotate credentials if they were ever exposed.

## 2) Run Release Checks

```bash
bash scripts/public_release_check.sh
```

## 3) Review Changes

```bash
git add .
git diff --cached
```

## 4) Required Project Files

- README.md
- INSTALLATION.md
- USAGE.md
- CONTRIBUTING.md
- SECURITY.md
- LICENSE
- .env.example

## 5) Attribution

When redistributing or integrating, keep attribution to TechBM Solutions developers visible in docs/UI where practical.
