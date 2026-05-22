# Solis Battery Monitor API

Turn raw inverter data into practical energy decisions.

This project gives homeowners and energy automation teams a reliable API for live battery SOC and weather-aware surplus consumption decisions. It is designed to help you consume smartly when production is strong and preserve battery when conditions are poor.

Built and maintained by TechBM Solutions developers.

## Free To Use

This project is offered for free to the community.

- No paywall.
- No monetization model.
- Open usage for personal and professional automation scenarios.

If this project helps you, please keep attribution visible so people know it was created by TechBM Solutions developers.

## Why This Project

- Convert Solis battery telemetry into actionable automation signals.
- Enable extra consumption when conditions are right: full SOC, daylight, and no rain.
- Integrate quickly with Home Assistant, Node-RED, custom scripts, or any HTTP-capable tool.
- Keep operations simple with a clean FastAPI interface and optional API token security.

## Core Capabilities

- Live SOC endpoint sourced from Solis web detail data.
- Decision endpoint for surplus consumption control.
- Optional webhook reporting when battery reaches full threshold.
- Optional API auth for external automation tools.
- Dashboard page for quick visual validation.

## Documentation Map

- Setup and local installation: [INSTALLATION.md](INSTALLATION.md)
- API and automation usage: [USAGE.md](USAGE.md)
- Public publishing checklist: [PUBLIC_RELEASE.md](PUBLIC_RELEASE.md)
- Contribution process: [CONTRIBUTING.md](CONTRIBUTING.md)
- Vulnerability reporting and security policy: [SECURITY.md](SECURITY.md)
- Community behavior standards: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Dependency update automation: [.github/dependabot.yml](.github/dependabot.yml)
- CI workflow: [.github/workflows/ci.yml](.github/workflows/ci.yml)

## Quick Start

```bash
make setup
make run
```

In another terminal:

```bash
make live
make decision
```

## Team Credit

This project is developed by TechBM Solutions developers, focused on practical energy automation, operational reliability, and production-ready integrations.

## Attribution Request

If you fork, deploy, or integrate this project, please keep one visible mention such as:

- "Powered by Solis Battery Monitor API by TechBM Solutions developers"

This helps the community identify the original developers and supports future open work.