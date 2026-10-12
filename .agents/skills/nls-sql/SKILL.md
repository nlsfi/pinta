---
name: nls-sql
description: NLS SQL conventions for writing, reviewing, and migrating SQL safely across schemas, transactions, and performance-sensitive queries.
---

## Safety  <!-- markdownlint-disable-line MD041 -->

- Never run `DROP`, `TRUNCATE`, `DELETE`, or `UPDATE` without a `WHERE` clause against a real
  database without explicit confirmation from a human. Always show the statement first.
- Prefer additive, reversible migrations. If a migration is destructive (drops a column, table,
  or constraint), call this out explicitly and make sure a rollback path exists.
- Never fabricate table or column names. Inspect the actual schema (migration files, ORM models,
  or database introspection tools) before writing a query.
- Do not commit generated data, credentials, or connection strings. Use environment variables or
  the project's existing secrets mechanism.

## Query style

- Write SQL keywords in `UPPER CASE` and identifiers in `lower_snake_case`, unless the codebase
  uses a different convention; match what exists.
- Prefer explicit column lists over `SELECT *` in application code and views. Use `SELECT *` only
  for ad hoc exploration.
- Always qualify columns with a table alias once a query joins more than one table.
- Use `JOIN ... ON` syntax, not comma joins with join conditions in `WHERE`.
- Use CTEs (`WITH`) to break up complex queries into named, readable steps.
- Format multi-line SQL consistently: one clause per line (`SELECT`, `FROM`, `WHERE`, `GROUP BY`,
  `ORDER BY`), with conditions aligned under their clause.

## Security

- Never build SQL by concatenating or interpolating untrusted input into query text.
- Always use parameterized queries / bound variables through the project's database driver or ORM.
- Treat this as non-negotiable, even for internal or read-only endpoints.
- For dynamic identifiers (table or column names), validate against an allow-list; values should
  still be parameterized.

## Schema changes and migrations

- Every schema change should go through the project's migration tool; do not hand-edit production
  databases.
- Keep one logical change per migration. Avoid bundling unrelated data backfills with schema
  changes.
- Add `NOT NULL` columns with a `DEFAULT`, or backfill in a separate step before enforcing
  non-null.
- New foreign keys and columns used in `WHERE`/`JOIN`/`ORDER BY` usually need an index. Check
  whether an existing index already covers the access pattern.
- Name constraints and indexes explicitly so future migrations can reference them safely.

## Performance

- For queries touching large tables, consider whether indexes support filter/join/sort patterns.
- Avoid `N+1` query patterns; prefer a single query with appropriate joins/aggregation.
- Be explicit about pagination (`LIMIT`/`OFFSET` or keyset pagination) for potentially unbounded
  result sets.
- Avoid functions or type casts on indexed columns in `WHERE` unless there is a matching
  expression index.
- When available, inspect query plans (`EXPLAIN` or equivalent) before claiming performance gains.

## Transactions

- Wrap multi-statement writes that must succeed or fail together in an explicit transaction.
- Keep transactions short; do not hold them open across network calls or long-running logic.
- Specify a non-default isolation level only when required, and explain why.

## Testing and review

- New queries or migrations that change behavior should be tested against a real test database,
  not only mocks.
- Verify generated SQL against the actual schema (table/column names, types, and nullability).
- In reviews, call out potential regressions: locking behavior, index usage, migration downtime,
  and rollback safety.

## Dialect guidance

- Prefer generic SQL unless the project clearly targets a specific engine.
- If the repository uses a specific dialect (for example, PostgreSQL), prefer that dialect's
  idioms when they improve readability, correctness, or performance.
- If dialect-specific behavior matters and is not documented, state assumptions and ask before
  finalizing.

## When unsure

- If index strategy, isolation level, or migration approach depends on data volume or access
  patterns, say so and ask instead of guessing.
