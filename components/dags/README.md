# Airflow Workflow component

## Local Airflow Development

Start a local standalone Airflow (running in a dev-container) for development purposes from the root of the repository:

```bash
make airflow-start
```

After execution, the Airflow logs will appear in the terminal, and the admin user password for the web interface can be
found in the file `.airflow/simple_auth_manager_passwords.json.generated`.

Once started, Airflow can be accessed via browser at <http://localhost:8080>.

The **PORTS** tab in the terminal panel also shows which port the Airflow webserver is running on, and VS Code
provides "Open in browser" buttons.

If necessary, code changes can be updated for Airflow use immediately by running the command `airflow dags reserialize`
or `make airflow-reserialize` from the root of the repository.
Airflow also automatically updates DAG file changes periodically.

## Updating Airflow

* Update the Airflow version with `uv add --optional airflow apache-airflow[postgres,standard]==3.1.8 --constraint https://raw.githubusercontent.com/apache/airflow/constraints-3.1.8/constraints-3.12.txt`
  * Replace versions with the desired Airflow version and python version.
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
