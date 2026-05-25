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
