# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest

from pinta_common import Settings


def test_db_job_writer_role_reads_environment(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DB_JOB_WRITER_ROLE", "some_writer_role")

    assert Settings.DB_JOB_WRITER_ROLE == "some_writer_role"


def test_db_job_writer_role_defaults_when_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DB_JOB_WRITER_ROLE", raising=False)

    assert Settings.DB_JOB_WRITER_ROLE == "pinta_writer"
