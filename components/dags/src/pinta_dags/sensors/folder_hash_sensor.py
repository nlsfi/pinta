# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

"""Sensor that detects changes in production area folders using file stat hashes."""

import hashlib
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from airflow.exceptions import AirflowSkipException
from airflow.sdk import BaseSensorOperator, Variable
from airflow.utils.context import Context


class FolderHashSensor(BaseSensorOperator):
    """Detect changes in production area folders using stat-based file hashing."""

    template_fields: Sequence[str] = ("base_path",)

    def __init__(self, *, base_path: str, **kwargs: Any) -> None:  # noqa: ANN401
        super().__init__(**kwargs)
        self.base_path = base_path

    def _hash_folder(self, folder_path: Path) -> str:
        h = hashlib.sha256()
        for dir_path, _, files in os.walk(folder_path):
            for f in sorted(files):
                p = Path(dir_path) / f
                stat = p.stat()
                data = f"{p}:{stat.st_size}:{stat.st_mtime}"
                h.update(data.encode())
        return h.hexdigest()

    def _find_changed_folders(self) -> list[dict[str, str]]:
        changed = []
        base = Path(self.base_path)
        for year_dir in sorted(base.iterdir()):
            if not year_dir.is_dir():
                continue
            for area_dir in sorted(year_dir.iterdir()):
                if not area_dir.is_dir():
                    continue
                new_hash = self._hash_folder(area_dir)
                stored_hash = Variable.get(area_dir.name, default=None)
                if stored_hash != new_hash:
                    changed.append(
                        {
                            "folder_path": str(area_dir.relative_to(base)),
                            "new_hash": new_hash,
                        }
                    )
        return changed

    def poke(self, context: Context) -> bool:  # noqa: ARG002
        """Return True if any production area folder has changed."""
        return len(self._find_changed_folders()) > 0

    def execute(self, context: Context) -> list[dict[str, str]]:  # noqa: ARG002
        """Check for folder changes once and either skip or return results."""
        changed = self._find_changed_folders()
        if not changed:
            msg = "No changes detected in production area folders"
            raise AirflowSkipException(msg)
        return changed
