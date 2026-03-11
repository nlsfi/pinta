# Database component

## Creating migrations

To create migrations modify database models first.
Make sure to have the models imported in [env.py](./migrations/env.py)
by adding them into [models.all](./src/pinta_db/models/all.py) module.

After models have been modified, run:

```bash
uv run alembic revision --autogenerate -m "Migration description" --rev-id="migration_id"
```

This command will generate a new migration file based on the changes made to the models.

Check the created migration file and make sure it is correct. Remember to commit it in the repository.

## Running migrations

To run migrations in development, in root of the project, run:

```bash
docker-compose run --rm ansible
```

In development, you can also run migrations manually by running:

```bash
uv run alembic upgrade head
```

But this does not run migrations to test databases.
