# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.


class AirflowClientError(Exception):
    pass


class AirflowAuthError(AirflowClientError):
    pass


class AirflowUnreachableError(AirflowClientError):
    pass


class AirflowApiError(AirflowClientError):
    def __init__(self, status: int, message: str = "") -> None:
        full_message = message or f"Airflow returned status {status}"
        super().__init__(full_message)
        self.status = status
        self.message = full_message


class InvalidWorkflowParametersError(AirflowClientError):
    def __init__(self, message: str = "") -> None:
        full_message = message or "Invalid workflow parameters"
        super().__init__(full_message)
        self.message = full_message


class DagNotFoundForTagError(AirflowClientError):
    def __init__(self, tag: str) -> None:
        super().__init__(f"No DAG with tag '{tag}'")
        self.tag = tag


class MultipleDagsForTagError(AirflowClientError):
    def __init__(self, tag: str, dag_ids: list[str]) -> None:
        super().__init__(f"Multiple DAGs match tag '{tag}': {dag_ids}")
        self.tag = tag
        self.dag_ids = dag_ids


class ProductionAreaNotFoundError(Exception):
    def __init__(self, production_area_id: str) -> None:
        super().__init__(f"No production area with id '{production_area_id}'")
        self.production_area_id = production_area_id


class DatabaseUnreachableError(Exception):
    """Raised when a database connection or query fails at the transport level."""


class JobDatabaseProtectedError(Exception):
    """Raised when the database name is not one a production area may drop."""

    def __init__(self, database_name: str) -> None:
        super().__init__(f"Database '{database_name}' must not be deleted")
        self.database_name = database_name


class JobDatabaseNotDeletableError(Exception):
    """Raised when the production area's state does not allow dropping its db."""

    def __init__(self, production_area_id: str, processing_status: str) -> None:
        super().__init__(
            f"Production area '{production_area_id}' cannot have its database "
            f"deleted while its processing status is '{processing_status}'"
        )
        self.production_area_id = production_area_id
        self.processing_status = processing_status


class JobDatabaseUnreachableError(Exception):
    """Raised when the job database cluster cannot be reached."""


class JobDatabaseDropFailedError(Exception):
    """Raised when the job cluster refuses to drop the database."""

    def __init__(self, database_name: str, detail: str) -> None:
        super().__init__(f"Failed to drop database '{database_name}': {detail}")
        self.database_name = database_name
