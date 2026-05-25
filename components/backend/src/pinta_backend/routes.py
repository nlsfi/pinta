# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

from typing import Annotated

import fastapi

from pinta_backend import airflow_client, exceptions, models
from pinta_backend.i18n import _, get_language

router = fastapi.APIRouter(tags=["default"])

AirflowClientDependency = Annotated[
    airflow_client.AirflowClient,
    fastapi.Depends(airflow_client.get_airflow_client),
]


@router.get("/health")
async def get_health() -> models.ApiHealth:
    """Return app health status."""
    return models.ApiHealth(parsed_language=get_language())


@router.get("/hello-world", tags=["default"])
async def get_foo() -> dict[str, str]:
    """Return app health status."""
    return {"message": _("Hello World")}


@router.post(
    "/workflows/{dag_tag}",
    status_code=fastapi.status.HTTP_202_ACCEPTED,
    responses={
        400: {"model": models.ErrorResponse},
        404: {"model": models.ErrorResponse},
        409: {"model": models.ErrorResponse},
        502: {"model": models.ErrorResponse},
    },
)
async def trigger_workflow(
    dag_tag: str,
    client: AirflowClientDependency,
    payload: models.WorkflowTriggerRequest | None = None,
) -> models.WorkflowRunStarted:
    """Trigger the Airflow DAG carrying ``dag_tag`` and return its run id."""
    parameters = payload.parameters if payload is not None else None
    try:
        run = await client.trigger_dag_by_tag(dag_tag, conf=parameters)
    except exceptions.InvalidWorkflowParametersError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_400_BAD_REQUEST,
            detail=_("Invalid workflow parameters: {error}.").format(error=exc.message),
        ) from exc
    except exceptions.DagNotFoundForTagError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_404_NOT_FOUND,
            detail=_("No workflow found for tag '{tag}'.").format(tag=exc.tag),
        ) from exc
    except exceptions.MultipleDagsForTagError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_("Multiple workflows found for tag '{tag}'.").format(tag=exc.tag),
        ) from exc
    except exceptions.AirflowAuthError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
            detail=_("Failed to authenticate against Airflow."),
        ) from exc
    except exceptions.AirflowUnreachableError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
            detail=_("Airflow is not reachable."),
        ) from exc
    except exceptions.AirflowApiError as exc:
        raise fastapi.HTTPException(
            status_code=fastapi.status.HTTP_502_BAD_GATEWAY,
            detail=_("Airflow returned an error: {error}.").format(error=exc.message),
        ) from exc

    return models.WorkflowRunStarted(
        message=_("Workflow run started."),
        dag_id=run.dag_id,
        dag_run_id=run.dag_run_id,
    )
