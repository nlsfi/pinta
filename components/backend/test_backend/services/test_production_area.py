# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import datetime
import uuid
from unittest import mock

import pytest
import sqlalchemy.exc
from pinta_db import constants
from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea
from pytest_mock import MockerFixture

from pinta_backend import exceptions
from pinta_backend.services import production_area


def _make_area(status: ProcessingStatus) -> ProductionArea:
    return ProductionArea(
        id=uuid.uuid4(),
        name="area",
        processing_status=status,
        geom="MultiPolygon(((0 0, 1 0, 1 1, 0 1, 0 0)))",
    )


@pytest.fixture
def mock_session(mocker: MockerFixture) -> mock.MagicMock:
    """Patch ``primary_db_session`` to yield a mocked SQLModel session."""
    session = mock.MagicMock()
    session_cm = mock.MagicMock()
    session_cm.__enter__.return_value = session
    session_cm.__exit__.return_value = False
    mocker.patch.object(
        production_area.db, "primary_db_session", return_value=session_cm
    )
    return session


def _load(session: mock.MagicMock, area: ProductionArea | None) -> None:
    session.exec.return_value.one_or_none.return_value = area


def test_mark_as_queued_with_none_id_is_a_no_op(mocker: MockerFixture) -> None:
    mock_session_cm = mocker.patch.object(production_area.db, "primary_db_session")

    with production_area.mark_as_queued(None) as yielded:
        assert yielded is None

    mock_session_cm.assert_not_called()


def test_mark_as_queued_raises_when_area_missing(
    mock_session: mock.MagicMock,
) -> None:
    _load(mock_session, None)
    area_id = str(uuid.uuid4())

    with (
        pytest.raises(exceptions.ProductionAreaNotFoundError) as exc_info,
        production_area.mark_as_queued(area_id),
    ):
        pass  # pragma: no cover -- never entered

    assert exc_info.value.production_area_id == area_id
    mock_session.commit.assert_not_called()


def test_mark_as_queued_sets_queued_status_and_commits(
    mock_session: mock.MagicMock,
) -> None:
    area = _make_area(ProcessingStatus.NOT_STARTED)
    _load(mock_session, area)

    with production_area.mark_as_queued(str(area.id)) as yielded:
        assert yielded is area
        assert area.processing_status == ProcessingStatus.QUEUED

    assert area.processing_status == ProcessingStatus.QUEUED
    assert mock_session.commit.call_count == 1


def test_mark_as_queued_uses_db_override_from_context(
    mock_session: mock.MagicMock,
    mocker: MockerFixture,
) -> None:
    area = _make_area(ProcessingStatus.NOT_STARTED)
    _load(mock_session, area)
    mocker.patch.object(
        production_area.db_context,
        "get_db_name_override",
        return_value="pinta_test_gw0",
    )

    with production_area.mark_as_queued(str(area.id)):
        pass

    production_area.db.primary_db_session.assert_called_once_with("pinta_test_gw0")


def test_mark_as_queued_uses_no_override_when_context_unset(
    mock_session: mock.MagicMock,
    mocker: MockerFixture,
) -> None:
    area = _make_area(ProcessingStatus.NOT_STARTED)
    _load(mock_session, area)
    mocker.patch.object(
        production_area.db_context, "get_db_name_override", return_value=None
    )

    with production_area.mark_as_queued(str(area.id)):
        pass

    production_area.db.primary_db_session.assert_called_once_with(None)


def test_mark_as_queued_restores_previous_status_on_exception(
    mock_session: mock.MagicMock,
) -> None:
    area = _make_area(ProcessingStatus.COMPLETED)
    _load(mock_session, area)

    error = RuntimeError("boom")
    with (
        pytest.raises(RuntimeError, match="boom"),
        production_area.mark_as_queued(str(area.id)),
    ):
        raise error

    assert area.processing_status == ProcessingStatus.COMPLETED
    # First commit marks queued, second commit restores.
    assert mock_session.commit.call_count == 2


@pytest.mark.parametrize(
    "failing_call",
    ["load", "commit"],
    ids=["operational_error_on_load", "operational_error_on_commit"],
)
def test_mark_as_queued_translates_operational_error_to_database_unreachable(
    mock_session: mock.MagicMock,
    failing_call: str,
) -> None:
    operational_error = sqlalchemy.exc.OperationalError(
        "stmt", {}, Exception("conn refused")
    )
    if failing_call == "load":
        mock_session.exec.side_effect = operational_error
    else:
        _load(mock_session, _make_area(ProcessingStatus.NOT_STARTED))
        mock_session.commit.side_effect = operational_error

    with (
        pytest.raises(exceptions.DatabaseUnreachableError),
        production_area.mark_as_queued(str(uuid.uuid4())),
    ):
        pass


@pytest.fixture
def mock_drop_database(mocker: MockerFixture) -> mock.MagicMock:
    """Patch the job-db admin connection and the DROP DATABASE helper."""
    connection = mock.MagicMock()
    connection_cm = mock.MagicMock()
    connection_cm.__enter__.return_value = connection
    connection_cm.__exit__.return_value = False
    mocker.patch.object(
        production_area.db, "job_db_admin_connection", return_value=connection_cm
    )
    return mocker.patch.object(
        production_area.database_utils, "drop_database", autospec=True
    )


@pytest.fixture(autouse=True)
def job_template_name(monkeypatch: pytest.MonkeyPatch) -> str:
    """Pin the template name, which `Settings` reads straight from the env."""
    monkeypatch.setenv("DB_JOB_TEMPLATE_NAME", "job_template")
    return "job_template"


def _make_area_with_database(
    database_name: str | None,
    status: ProcessingStatus = ProcessingStatus.COMPLETED,
) -> ProductionArea:
    area = _make_area(status)
    area.database_name = database_name
    area.processing_status_last_updated = datetime.datetime(2026, 1, 1, 12, 0)
    return area


def test_delete_job_database_drops_database_and_resets_area(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    area = _make_area_with_database("job_area_1")
    _load(mock_session, area)

    dropped = production_area.delete_job_database(str(area.id))

    assert dropped == "job_area_1"
    mock_drop_database.assert_called_once()
    assert mock_drop_database.call_args.args[1] == "job_area_1"
    assert area.database_name is None
    assert area.processing_status == ProcessingStatus.NOT_STARTED
    mock_session.commit.assert_called_once_with()


def test_delete_job_database_leaves_the_timestamp_to_the_trigger(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    """The reset is a status change like any other, so the
    ``update_processing_timestamp`` trigger stamps it: the service must not
    write ``processing_status_last_updated`` itself."""
    area = _make_area_with_database("job_area_1")
    _load(mock_session, area)
    timestamps: list[datetime.datetime | None] = []
    mock_session.commit.side_effect = lambda: timestamps.append(
        area.processing_status_last_updated
    )

    production_area.delete_job_database(str(area.id))

    assert timestamps == [datetime.datetime(2026, 1, 1, 12, 0)]
    assert area.processing_status_last_updated == datetime.datetime(2026, 1, 1, 12, 0)


def test_delete_job_database_resets_area_without_database_name(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    area = _make_area_with_database(None, ProcessingStatus.FAILURE)
    _load(mock_session, area)

    dropped = production_area.delete_job_database(str(area.id))

    assert dropped is None
    mock_drop_database.assert_not_called()
    assert area.processing_status == ProcessingStatus.NOT_STARTED
    mock_session.commit.assert_called_once_with()


def test_delete_job_database_raises_when_area_missing(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    _load(mock_session, None)
    area_id = str(uuid.uuid4())

    with pytest.raises(exceptions.ProductionAreaNotFoundError) as exc_info:
        production_area.delete_job_database(area_id)

    assert exc_info.value.production_area_id == area_id
    mock_drop_database.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.parametrize(
    "database_name",
    [
        "job_template",  # carries the prefix, but is the template itself
        "pinta",
        "postgres",
        "template1",
        "jobs_area_1",  # prefix must be `job_`, not merely start with `job`
        "job",
        "",
    ],
    ids=repr,
)
def test_delete_job_database_refuses_to_drop_protected_databases(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
    database_name: str,
) -> None:
    area = _make_area_with_database(database_name)
    _load(mock_session, area)

    with pytest.raises(exceptions.JobDatabaseProtectedError) as exc_info:
        production_area.delete_job_database(str(area.id))

    assert exc_info.value.database_name == database_name
    mock_drop_database.assert_not_called()
    # The area keeps pointing at the database that was not dropped.
    assert area.database_name == database_name
    mock_session.commit.assert_not_called()


def test_delete_job_database_drops_the_name_the_dags_provision(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    """The DAGs name job databases `job_{production_area_id}`."""
    area = _make_area(ProcessingStatus.COMPLETED)
    area.database_name = f"{constants.JOB_DATABASE_NAME_PREFIX}{area.id}"
    _load(mock_session, area)

    dropped = production_area.delete_job_database(str(area.id))

    assert dropped == f"job_{area.id}"
    assert mock_drop_database.call_args.args[1] == f"job_{area.id}"


def test_delete_job_database_refuses_a_renamed_template(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The template is protected under whatever name the environment gives it."""
    monkeypatch.setenv("DB_JOB_TEMPLATE_NAME", "job_master")
    area = _make_area_with_database("job_master")
    _load(mock_session, area)

    with pytest.raises(exceptions.JobDatabaseProtectedError):
        production_area.delete_job_database(str(area.id))

    mock_drop_database.assert_not_called()


@pytest.mark.parametrize(
    "status",
    [ProcessingStatus.COMPLETED, ProcessingStatus.FAILURE],
    ids=str,
)
def test_delete_job_database_allows_finished_runs(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
    status: ProcessingStatus,
) -> None:
    area = _make_area_with_database("job_area_1", status)
    _load(mock_session, area)

    assert production_area.delete_job_database(str(area.id)) == "job_area_1"

    mock_drop_database.assert_called_once()
    assert area.processing_status == ProcessingStatus.NOT_STARTED


@pytest.mark.parametrize(
    "status",
    [
        ProcessingStatus.NOT_STARTED,
        ProcessingStatus.QUEUED,
        ProcessingStatus.STARTED,
    ],
    ids=str,
)
def test_delete_job_database_refuses_unfinished_runs(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
    status: ProcessingStatus,
) -> None:
    """A run still in flight owns the database, so it must not be dropped."""
    area = _make_area_with_database("job_area_1", status)
    _load(mock_session, area)

    with pytest.raises(exceptions.JobDatabaseNotDeletableError) as exc_info:
        production_area.delete_job_database(str(area.id))

    assert exc_info.value.production_area_id == str(area.id)
    assert exc_info.value.processing_status == status.value
    mock_drop_database.assert_not_called()
    # Neither the database name nor the status is touched.
    assert area.database_name == "job_area_1"
    assert area.processing_status == status
    mock_session.commit.assert_not_called()


def test_delete_job_database_checks_the_status_before_the_database_name(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    """A busy area reports its status, not that its database looks droppable."""
    area = _make_area_with_database("postgres", ProcessingStatus.STARTED)
    _load(mock_session, area)

    with pytest.raises(exceptions.JobDatabaseNotDeletableError):
        production_area.delete_job_database(str(area.id))


def test_delete_job_database_translates_job_cluster_outage(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    """A job-cluster outage is reported separately from a primary-db outage."""
    mock_drop_database.side_effect = sqlalchemy.exc.OperationalError(
        "stmt", {}, Exception("conn refused")
    )
    area = _make_area_with_database("job_area_1")
    _load(mock_session, area)

    with pytest.raises(exceptions.JobDatabaseUnreachableError):
        production_area.delete_job_database(str(area.id))

    mock_session.commit.assert_not_called()


def test_delete_job_database_translates_a_refused_drop(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    """A refused DROP is a failed request, not an outage."""
    mock_drop_database.side_effect = sqlalchemy.exc.ProgrammingError(
        "stmt", {}, Exception("permission denied for database job_area_1")
    )
    area = _make_area_with_database("job_area_1")
    _load(mock_session, area)

    with pytest.raises(exceptions.JobDatabaseDropFailedError) as exc_info:
        production_area.delete_job_database(str(area.id))

    assert exc_info.value.database_name == "job_area_1"
    assert area.database_name == "job_area_1"
    mock_session.commit.assert_not_called()


def test_delete_job_database_uses_db_override_from_context(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
    mocker: MockerFixture,
) -> None:
    area = _make_area_with_database("job_area_1")
    _load(mock_session, area)
    mocker.patch.object(
        production_area.db_context,
        "get_db_name_override",
        return_value="pinta_test_gw0",
    )

    production_area.delete_job_database(str(area.id))

    production_area.db.primary_db_session.assert_called_once_with("pinta_test_gw0")


def test_delete_job_database_translates_operational_error_to_database_unreachable(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    mock_session.exec.side_effect = sqlalchemy.exc.OperationalError(
        "stmt", {}, Exception("conn refused")
    )

    with pytest.raises(exceptions.DatabaseUnreachableError):
        production_area.delete_job_database(str(uuid.uuid4()))


def test_delete_job_database_does_not_reset_area_when_drop_fails(
    mock_session: mock.MagicMock,
    mock_drop_database: mock.MagicMock,
) -> None:
    area = _make_area_with_database("job_area_1")
    _load(mock_session, area)
    mock_drop_database.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        production_area.delete_job_database(str(area.id))

    assert area.database_name == "job_area_1"
    mock_session.commit.assert_not_called()
