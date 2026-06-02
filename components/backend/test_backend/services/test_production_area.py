# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import uuid
from unittest import mock

import pytest
import sqlalchemy.exc
from pinta_db.primary_db.models.management import ProcessingStatus, ProductionArea
from pytest_mock import MockerFixture

from pinta_backend.exceptions import (
    DatabaseUnreachableError,
    ProductionAreaNotFoundError,
)
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
        pytest.raises(ProductionAreaNotFoundError) as exc_info,
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
        pytest.raises(DatabaseUnreachableError),
        production_area.mark_as_queued(str(uuid.uuid4())),
    ):
        pass
