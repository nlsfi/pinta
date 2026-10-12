---
name: nls-airflow
description: NLS Airflow DAG conventions for scheduling, task design, and operational safety in Airflow-based data workflows.
---

## Scope  <!-- markdownlint-disable-line MD041 -->

- Apply this skill when editing Airflow DAGs, operators, sensors, or scheduling configuration.
- Keep Airflow-specific conventions here as they are defined for NLS repositories.

## DAG structure and registration

- Prefer `@dag(...)` decorators over legacy `DAG(...)` context managers unless the repository already standardizes on legacy style.
- Use a DAG factory function and create the DAG object once, then register it via `globals()[DAG_ID] = create_dag()` when the project uses module discovery.
- Keep `dag_id` and task IDs stable; changing IDs breaks historical views and external dependencies.
- Set `max_active_runs` explicitly for DAGs that can overload shared systems when run concurrently.

## Scheduling and parameters

- Use an explicit `schedule` (`None`, cron, or `timedelta`) and avoid relying on defaults.
- Set `start_date` intentionally and keep it deterministic; do not use dynamic values like `datetime.now()`.
- Define runtime params with `Param(...)` when values are user-provided through manual triggers.
- Keep parameter names descriptive and validate required values early in task logic.

## Task design

- Prefer TaskFlow decorators (`@task`, `@task.docker`, `@task.short_circuit`) over ad hoc operators when they fit.
- Keep shared container/operator arguments in a central config object to avoid drift across tasks.
- Add type hints to task inputs and outputs; treat them as part of the DAG contract.
- Keep task bodies focused on orchestration boundaries; move reusable business logic into importable modules.

## Concurrency and mapping

- Use `expand(...)` for data-driven fan-out instead of hand-built loops of static tasks.
- Use `partial(...)` to bind static kwargs before mapping dynamic inputs.
- Limit parallelism for expensive tasks with task-level controls such as `max_active_tis_per_dag`.
- Balance throughput and infrastructure safety; document non-obvious concurrency limits in code comments.

## Flow control and trigger rules

- Use `>>` or `chain(...)` to make dependencies explicit and easy to scan.
- Use `@task.short_circuit` for skip-based branches where downstream work should be bypassed.
- Set non-default trigger rules (for example, `TriggerRule.NONE_FAILED`) explicitly where partial upstream skips are expected.
- Keep branching conditions deterministic and side-effect free.

## Sensors and waiting behavior

- Prefer purpose-built sensors for polling external state instead of long-running Python loops in tasks.
- For custom sensors, subclass `BaseSensorOperator`, define `template_fields` when needed, and keep `poke(...)` idempotent.
- Return clear outcomes from `execute(...)`; use `AirflowSkipException` for legitimate no-op paths.
- Tune poke interval/timeouts for external systems to avoid unnecessary load.

## Configuration and variables

- Centralize Airflow Variable names in one module (for example, enum/constants) to avoid typos.
- Parse and validate variable values defensively; fail fast with actionable errors when values are missing or invalid.
- Keep retry counts and retry delays in shared config defaults instead of duplicating literals per task.
- Build connection strings through helper functions/templates when the same pattern is reused.

## Operational safety

- Raise explicit exceptions with actionable messages when validation fails; avoid silent fallbacks.
- Use `AirflowSkipException` for expected skip conditions and hard failures for data integrity issues.
- Make side effects idempotent where feasible so retries do not corrupt state.
- Do not log secrets, connection passwords, or full credential-bearing URIs.

## Imports, docs, and style

- Match the repository import style; lazy-import heavy dependencies inside containerized tasks when startup cost matters.
- Add concise module and function docstrings for non-trivial DAGs and custom operators/sensors.
- Keep SQL, filesystem paths, and external endpoints explicit and reviewable in code.
- Keep DAG files readable: small helper functions, descriptive names, and no hidden magic constants.
