# CI/CD, secrets, containers and deployment config

Load when the repo contains pipelines, container definitions, Ansible, pre-commit config or
deployment configuration. These are part of A02 (misconfiguration), A03 (supply chain) and A08
(integrity): a compromised pipeline ships compromised software with valid credentials.

## Secrets

- Run gitleaks on both the working tree and git history. A secret removed in a later commit is
  still exposed; the fix is rotation, not deletion.
- Also look manually in places scanners miss: notebooks (`.ipynb` outputs), `.env.example` files
  with real values, test fixtures, QGIS project files, Ansible inventories and `group_vars`
  without Vault, Docker Compose files, `settings*.py`, connection strings in docs.
- Check `.gitignore` covers `.env`, local config, keys and certificate files.
- Report: location, secret type, whether it is in history only, and "rotate" as the fix. Redact.

## Jenkins (Jenkinsfile, shared libraries)

- Secrets interpolated with Groovy double quotes: `sh "curl -u ${USER}:${PASS} ..."` puts the
  secret into the command line (visible in process lists, may leak in logs). Good: single quotes
  so the shell expands the environment variable: `sh 'curl -u "$USER:$PASS" ...'` inside
  `withCredentials`.
- Parameters (`params.X`) interpolated into `sh` steps: command injection by anyone allowed to
  build with parameters.
- Pipelines loading shared libraries or scripts from mutable refs (branches) of other repos.
- `curl ... | sh`, downloading tools without checksum verification.
- Agents with broad credentials used for untrusted branches or pull requests.

## GitHub Actions

- Actions referenced by tag or branch instead of full commit SHA (the tj-actions/changed-files
  compromise, CVE-2025-30066, rewrote tags). Run zizmor if available.
- `pull_request_target` or `workflow_run` workflows that check out and run PR code with secrets.
- Script injection: `${{ github.event.issue.title }}`, `${{ github.head_ref }}` and similar
  directly inside `run:`. Good: pass via `env:` and reference `"$VAR"`.
- Missing top-level `permissions:` (defaults may be write-all); `GITHUB_TOKEN` with more scope
  than needed; long-lived cloud keys instead of OIDC.
- Self-hosted runners used by workflows triggered from forks.

## Pre-commit

- Hooks pinned to tags (`rev: v1.2.3`) rather than full commit SHAs. Tags are mutable; hooks run
  code on every developer's machine. `pre-commit autoupdate --freeze` pins SHAs.
- Hooks from unfamiliar repositories: review what they execute.

## Containers (Dockerfile, Containerfile, Compose, Podman)

- Base images by mutable tag (`python:3.12`, `latest`) rather than digest (`@sha256:...`), or
  from untrusted registries.
- Running as root (no `USER`), unnecessary packages, build tools left in the final image (use
  multi-stage builds).
- Secrets in `ENV`, `ARG` or copied files (they persist in layers). Good: build secrets
  (`RUN --mount=type=secret`) and runtime injection.
- `ADD` from URLs, `curl | sh`, no checksum verification of downloaded artefacts.
- `pip install` without lockfile/hashes inside the image.
- Compose: `privileged: true`, host network, Docker socket mounts, default database passwords,
  ports published on `0.0.0.0` that should be internal.

## Ansible

- Secrets in plain text in vars/inventories instead of Ansible Vault or an external secret store;
  tasks handling secrets without `no_log: true` (secrets end up in logs and CI output).
- `validate_certs: false` on `uri`, `get_url`, package and API modules.
- `shell`/`command` with templated variables from inventories or extra-vars that less-trusted
  parties can influence; prefer purpose-built modules.
- `get_url` without `checksum`; repositories added without GPG key verification.
- Files and directories created with overly broad `mode`, or services running as root without
  need.
- Collections and roles from Galaxy or Git without version pinning (`requirements.yml`).
