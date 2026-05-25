# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import functools
import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import jsonschema
from airflow_client.client import ApiClient, Configuration
from airflow_client.client.api.dag_api import DAGApi
from airflow_client.client.api.dag_run_api import DagRunApi
from airflow_client.client.exceptions import (
    ApiException,
    BadRequestException,
    UnauthorizedException,
)
from airflow_client.client.models.dag_collection_response import (
    DAGCollectionResponse,
)
from airflow_client.client.models.dag_details_response import DAGDetailsResponse
from airflow_client.client.models.dag_run_response import DAGRunResponse
from airflow_client.client.models.trigger_dag_run_post_body import TriggerDAGRunPostBody
from fastapi import concurrency

from pinta_backend import airflow_auth, exceptions, settings

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class AirflowClient:
    """Async wrapper over apache-airflow-client with token-aware retry."""

    def __init__(self, app_settings: settings.Settings) -> None:
        self._settings = app_settings
        self._auth = airflow_auth.AirflowAuthenticator(app_settings)

    @property
    def _base_url(self) -> str:
        return self._auth.base_url

    async def trigger_dag_by_tag(
        self,
        tag: str,
        *,
        conf: dict[str, Any] | None = None,
    ) -> DAGRunResponse:
        """Find the DAG matching `tag` and trigger a run.

        Pre-validates `conf` against the DAG's params schema.

        Args:
            tag: Unique DAG tag to look up.
            conf: Optional configuration dict forwarded to the DAG run.
        """
        dag_id = await self._find_dag_id_by_tag(tag)
        await self._validate_params(dag_id, conf or {})

        def _trigger(api_client: ApiClient) -> DAGRunResponse:
            try:
                return DagRunApi(api_client).trigger_dag_run(
                    dag_id,
                    TriggerDAGRunPostBody(conf=conf),
                )
            except BadRequestException as exc:
                raise exceptions.InvalidWorkflowParametersError(
                    _extract_airflow_error_message(exc),
                ) from exc

        return await self._call_with_retry(_trigger)

    async def _find_dag_id_by_tag(self, tag: str) -> str:
        """Return the dag_id of the single DAG carrying `tag`."""

        def _list(api_client: ApiClient) -> DAGCollectionResponse:
            return DAGApi(api_client).get_dags(tags=[tag], tags_match_mode="any")

        collection = await self._call_with_retry(_list)
        matches = [d for d in collection.dags if any(t.name == tag for t in d.tags)]
        if not matches:
            raise exceptions.DagNotFoundForTagError(tag)
        if len(matches) > 1:
            raise exceptions.MultipleDagsForTagError(tag, [d.dag_id for d in matches])
        return matches[0].dag_id

    async def _validate_params(self, dag_id: str, conf: dict[str, Any]) -> None:
        """Validate `conf` against `dag_id`'s Airflow params schema."""

        def _fetch(api_client: ApiClient) -> DAGDetailsResponse:
            return DAGApi(api_client).get_dag_details(dag_id=dag_id)

        details = await self._call_with_retry(_fetch)
        schema = _build_param_schema(details.params or {})
        try:
            jsonschema.validate(conf, schema)
        except jsonschema.ValidationError as exc:
            raise exceptions.InvalidWorkflowParametersError(
                _format_jsonschema_error(exc),
            ) from exc

    async def _call_with_retry(self, fn: Callable[[ApiClient], T]) -> T:
        """Run an SDK call, retrying once with a fresh token on 401."""
        token = await self._auth.get_token()
        try:
            return await self._run_sync(fn, token)
        except UnauthorizedException:
            LOGGER.info("Airflow token rejected; refreshing and retrying")
        token = await self._auth.refresh_token()
        try:
            return await self._run_sync(fn, token)
        except UnauthorizedException as exc:
            msg = "Airflow rejected refreshed token"
            raise exceptions.AirflowAuthError(msg) from exc

    async def _run_sync(self, fn: Callable[[ApiClient], T], token: str) -> T:
        with ApiClient(
            Configuration(host=self._base_url, access_token=token)
        ) as api_client:
            try:
                return await concurrency.run_in_threadpool(fn, api_client)
            except UnauthorizedException:
                raise
            except ApiException as exc:
                status = int(exc.status or 0)
                if status == 0:
                    raise exceptions.AirflowUnreachableError(
                        exc.reason or "Airflow request failed",
                    ) from exc
                raise exceptions.AirflowApiError(status, exc.reason or "") from exc


@functools.lru_cache(maxsize=1)
def get_airflow_client() -> AirflowClient:
    """Return a process-wide AirflowClient instance."""
    return AirflowClient(settings.get_settings())


def _extract_airflow_error_message(exc: ApiException) -> str:
    """Pull a human-readable message out of an Airflow error response."""
    if exc.body:
        try:
            data = json.loads(exc.body)
        except (TypeError, ValueError):
            return str(exc.body)
        detail = data.get("detail") if isinstance(data, dict) else None
        if isinstance(detail, str):
            return detail
        if detail is not None:
            return json.dumps(detail)
    return exc.reason or "Bad request"


def _build_param_schema(params: dict[str, Any]) -> dict[str, Any]:
    """Convert an Airflow DAG params dict into a JSON Schema."""
    properties = {
        name: (spec.get("schema") if isinstance(spec, dict) else None) or {}
        for name, spec in params.items()
    }
    return {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }


def _format_jsonschema_error(exc: jsonschema.ValidationError) -> str:
    path = ".".join(str(p) for p in exc.absolute_path)
    return f"{path}: {exc.message}" if path else exc.message
