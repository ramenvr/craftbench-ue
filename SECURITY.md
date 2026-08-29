# Security policy

## Reporting a vulnerability

Please report security issues **privately**, not as a public issue.

Use GitHub's private reporting on this repository: **Security → Report a
vulnerability**. That opens a draft advisory visible only to the maintainers, and
it needs no email address from either side.

Useful things to include: what an attacker can do, the smallest reproduction you
have, and the commit you saw it on. We will confirm receipt and tell you what we
intend to do about it.

## Scope

This repository is a benchmark harness that runs on a developer's own machine
against their own Unreal Engine install. It is not a hosted service, so the
interesting surface is narrower than usual. In scope:

- **Anything that leaks a credential.** The harness handles your model API key.
  A path that writes it into a log, a run artifact, a transcript or a report is a
  real finding.
- **Agent escape from the write sandbox.** A submission that reaches outside the
  agent-writable prefixes, or that reaches the verifier's own code, defeats the
  measurement. Report it.
- **The dashboard web app.** `python -m tools.dashboard.web` exposes an
  unauthenticated `POST /api/launch` that spawns a real graded run and spends your
  API key. This is **known and documented**, and binding a non-loopback host
  requires an explicit `--allow-remote-launch` flag for that reason. A way to
  reach that endpoint *without* the flag, or a way to make it run something
  outside the intended argv, is in scope.
- **Command injection** through a task id, a model slug, a file path, or anything
  else that reaches a subprocess.

Out of scope:

- Unreal Engine itself, and Epic's plugins. Report those to Epic Games.
- The `aura-mcp` arm's runtime. It ships disclosed but not runnable — see
  [`THIRD-PARTY.md`](THIRD-PARTY.md) §4 — so there is nothing here to attack.
- A task's reference solution being discoverable by an agent that already has
  arbitrary read access to the machine. The fairness layer stops *discovery*, and
  says so; it was never a permission boundary.

## Supported versions

This project is released from `main`. Fixes land there; there are no maintained
release branches.
