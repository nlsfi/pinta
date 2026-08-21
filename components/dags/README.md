# Airflow Workflow component

## Development

By default, Airflow runs in a container, started from the repository root with Docker
Compose:

```bash
docker compose up -d
```

(or `make up`). This is the default Airflow used in development and e2e tests, available at
<http://localhost:8080>.

### Local development

Optionally run a local standalone Airflow on the host (in the dev-container) from the
repository root. This is mainly for testing Airflow version upgrades and as a backup:

```bash
make airflow-start
```

After execution, the Airflow logs will appear in the terminal. Passwords are pre-written
deterministically to `.airflow/simple_auth_manager_passwords.json.generated` from the values of `.env`.
Run `make airflow-clean airflow-start` to pick up changes to those passwords.

Once started, Airflow can be accessed via browser at <http://localhost:8080>.

The **PORTS** tab in the terminal panel also shows which port the Airflow webserver is running on, and VS Code
provides "Open in browser" buttons.

If necessary, code changes can be updated for Airflow use immediately by running the command `airflow dags reserialize`
or `make airflow-reserialize` from the root of the repository.
Airflow also automatically updates DAG file changes periodically.

#### Developing DAGs locally

If you want to run the load dem DAG, you can place test data inside the repo root `test_data` folder, which is automatically mounted to the processing container.

## DAG development practices

* When accessing any database, use `@task.docker` since database urls work only inside containers

## Updating Airflow

`numpy` and `scipy` are pinned in the DAG component because Airflow's upstream constraints file already fixes versions for the whole dependency set, but those two packages need to be kept under explicit control in this repository so the workspace can resolve the Airflow extra consistently across components. Pulling them out of the generated constraints file and pinning them in `pyproject.toml` makes upgrades repeatable and avoids resolution conflicts when `uv add` is run.

* Update the Airflow version in `components/dags/pyproject.toml` manually.
* Update required AIRFLOW_VERSION and PYTHON_VERSION in Makefile
* Fetch and normalize the matching constraints file with `make airflow-prepare-constraints`.
  * The helper downloads the upstream Apache Airflow constraints file for the selected Python version, removes the `numpy` and `scipy` pins, and writes a local modified copy under `components/dags/.airflow/constraints/`.
  * The helper prints the upstream `numpy` and `scipy` versions. Update the `numpy` and `scipy` pins in `components/dags/pyproject.toml` to match.
* If the backend Airflow client needs to stay in sync, update the pin in `components/backend/pyproject.toml` as well.
* Run `uv add --optional airflow apache-airflow[docker,postgres,standard]==<version> --constraint <path-to-modified-constraints>` from `components/dags`.
* Run tests and test standalone usage; remove warning filters or other workarounds required by the old version if
  necessary.

### Special Cases

If there is a need to update dependencies defined by the Airflow constraint file—for example, due to a vulnerability, a
bug, or a new feature in a specific provider package:

* Update the Ansible role's constraint file as needed, e.g., for a single package (add a comment explaining why it was
  updated from the original if necessary).
* Compile new requirements files locally (see commands at the top of the files).
* Test sufficiently.
* Deploy the update to the environments.

**NOTE:** Updating the shared constraint file for a single Airflow version will simultaneously push the new versions to
other environments if a deployment is performed (e.g., for a configuration update) before the update has been
sufficiently verified.
