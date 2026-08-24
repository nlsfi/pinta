# Copyright (C) 2026 Pinta QGIS Plugin Contributors.
#
#
# This file is part of Pinta QGIS Plugin.
#
# Pinta QGIS Plugin is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# Pinta QGIS Plugin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Pinta QGIS Plugin.  If not, see <https://www.gnu.org/licenses/>.

import enum
import functools
import logging
from collections.abc import Callable
from typing import Any, NoReturn, ParamSpec, TypeVar

import requests
from pinta_common import constants
from qgis.core import QgsSettings
from qgis.PyQt.QtCore import QLocale, QObject, pyqtSignal
from qgis_plugin_tools.tools.i18n import tr
from qgis_plugin_tools.tools.messages import MsgBar
from requests.exceptions import JSONDecodeError

from pinta_qgis_plugin import env, exceptions

LOGGER = logging.getLogger(__name__)
ParamsType = ParamSpec("ParamsType")
ReturnType = TypeVar("ReturnType")


class ApiEndpoint(enum.Enum):
    """Supported Pinta API endpoints."""

    workflows = "/workflows"
    production_areas = "/production-areas"


# Create a typed decorator wrapper
def handle_api_errors(
    endpoint: ApiEndpoint,
) -> Callable[[Callable[ParamsType, ReturnType]], Callable[ParamsType, ReturnType]]:
    """Decoration used to handle errors from API."""

    def decorator(
        function: Callable[ParamsType, ReturnType],
    ) -> Callable[ParamsType, ReturnType]:
        @functools.wraps(function)
        def wrapper(*args: ParamsType.args, **kwargs: ParamsType.kwargs) -> ReturnType:
            try:
                return function(*args, **kwargs)
            except requests.exceptions.ConnectionError as conn_error:
                raise exceptions.ApiConnectionError(conn_error) from conn_error
            except requests.exceptions.HTTPError as error:
                _raise_api_error(endpoint, _api_error_detail(error.response))

        return wrapper

    return decorator


class PintaAPIClient(QObject):
    """API client for Pinta Backend."""

    workflow_started = pyqtSignal(str, str)  # (dag_id, dag_run_id)
    job_database_deleted = pyqtSignal(str)  # (production_area_id)

    def __init__(self, base_url: str, timeout: int = 10) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept-Language": QgsSettings().value(
                    "locale/userLocale", QLocale().name()
                )
            }
        )
        if env.IS_DEVELOPMENT_MODE:
            self.session.headers["X-Pinta-Db-Name"] = env.PINTA_DB_NAME
        self._timeout = timeout

    @handle_api_errors(ApiEndpoint.workflows)
    def start_reference_dem_workflow(self, production_area_id: str) -> None:
        """Starts a DEM update workflow for the given production area."""
        self._start_workflow(
            constants.DAG_ID_CALCULATE_RASTERS_FOR_PRODUCTION_AREA,
            {
                "id": production_area_id,
                "calculate_reference_dem": True,
                "calculate_dem_diff": True,
                "cluster_diff_polygons": True,
                "initialize_dem_preview": True,
            },
            production_area_id=production_area_id,
        )
        MsgBar.info(
            tr("Reference DEM workflow task created successfully"), success=True
        )

    @handle_api_errors(ApiEndpoint.workflows)
    def start_dissolve_update_areas_workflow(self, production_area_id: str) -> None:
        """Starts a dissolve update areas workflow for the given production area."""
        self._start_workflow(
            constants.DAG_ID_DISSOLVE_UPDATE_AREAS,
            {"id": production_area_id},
            production_area_id=production_area_id,
        )
        MsgBar.info(
            tr("Dissolve update areas workflow task created successfully"),
            success=True,
        )

    @handle_api_errors(ApiEndpoint.workflows)
    def start_register_update_areas_workflow(self, production_area_id: str) -> None:
        """Starts a register update areas workflow for the given production area."""
        self._start_workflow(
            constants.DAG_ID_REGISTER_UPDATE_AREAS,
            {"id": production_area_id},
            production_area_id=production_area_id,
        )
        MsgBar.info(
            tr("Register update areas workflow task created successfully"),
            success=True,
        )

    @handle_api_errors(ApiEndpoint.production_areas)
    def delete_job_database(self, production_area_id: str) -> None:
        """Deletes the job database of the given production area."""
        LOGGER.info("Deleting job database of production area %s", production_area_id)
        response = self.session.delete(
            f"{self.base_url}{ApiEndpoint.production_areas.value}"
            f"/{production_area_id}/database",
            timeout=self._timeout,
        )
        response.raise_for_status()
        self.job_database_deleted.emit(production_area_id)
        MsgBar.info(
            tr("Production area database deleted successfully"),
            success=True,
        )

    def _start_workflow(
        self,
        dag_tag: str,
        parameters: dict[str, Any],
        production_area_id: str | None = None,
    ) -> None:
        LOGGER.info("Starting workflow %s", dag_tag)
        LOGGER.debug("Workflow %s parameters: %s", dag_tag, parameters)
        payload: dict[str, Any] = {"parameters": parameters}
        if production_area_id is not None:
            payload["production_area_id"] = production_area_id
        response = self.session.post(
            f"{self.base_url}{ApiEndpoint.workflows.value}/{dag_tag}",
            json=payload,
            timeout=self._timeout,
        )
        response.raise_for_status()
        run = response.json()
        self.workflow_started.emit(run["dag_id"], run["dag_run_id"])


@functools.lru_cache(maxsize=1)
def get_api_client() -> PintaAPIClient:
    """Returns a PintaAPIClient instance."""
    return PintaAPIClient(env.PINTA_BACKEND_URL)


def _raise_api_error(endpoint: ApiEndpoint, detail: str) -> NoReturn:
    match endpoint:
        case ApiEndpoint.workflows:
            raise exceptions.WorkflowNotStartedError(
                tr("Could not start workflow"), detail
            ) from None
        case ApiEndpoint.production_areas:
            raise exceptions.JobDatabaseNotDeletedError(
                tr("Could not delete production area database"), detail
            ) from None


def _api_error_detail(response: requests.Response | None) -> str:
    if response is not None:
        try:
            detail = response.json().get("detail")
        except (AttributeError, JSONDecodeError):
            detail = None
        if detail is not None:
            return str(detail)

        LOGGER.error("API request to %s failed: %s", response.url, response.text)

    return tr("Check log for more details")
