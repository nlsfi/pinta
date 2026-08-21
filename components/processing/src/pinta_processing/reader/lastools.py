# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.
import logging
import pathlib
import subprocess
import tempfile

from pinta_common import Settings

from pinta_processing import core
from pinta_processing.exceptions import LasToolsError
from pinta_processing.reader import readers

LOGGER = logging.getLogger(__name__)


class LASToolsReader(core.Stage):
    """Base class for LASTools readers."""

    executable = ""

    def __init__(
        self,
        input_path: pathlib.Path,
        crs: str,  # in format EPSG:xxxx
        extra_lastools_params: dict | None = None,
    ) -> None:
        self.input_path = input_path
        self.crs = crs
        self.extra_lastools_params = extra_lastools_params

    def process(self, data: core.RasterDataset | None) -> core.RasterDataset:  # noqa: ARG002
        """Run LASTools command and return the output as a RasterDataset."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_output_file = pathlib.Path(temp_dir) / "output.tif"
            command = self._get_command(temp_output_file)

            LOGGER.info("Running LASTools command: %s", " ".join(command))
            result = self._run_command(command, temp_dir)

            if result.returncode != 0:
                raise LasToolsError(
                    stage_name=self.__class__.__name__,
                    command=" ".join(command),
                    error_message=result.stderr,
                )
            if not temp_output_file.exists():
                raise LasToolsError(
                    stage_name=self.__class__.__name__,
                    command=" ".join(command),
                    error_message=f"Output file {temp_output_file} was not created",
                )

            return readers.RasterioReader(path=temp_output_file, crs=self.crs).process(
                None
            )

    def _run_command(
        self,
        command: list[str],
        working_directory: str,
    ) -> subprocess.CompletedProcess:
        result = subprocess.run(  # noqa: S603
            command, check=False, capture_output=True, text=True, cwd=working_directory
        )
        LOGGER.info("LASTools command output: %s", result.stdout)
        return result

    def _get_command(self, output_file: pathlib.Path) -> list[str]:
        base_command = [
            self.executable,
            "-i",
            str(self.input_path),
            "-o",
            str(output_file),
            "-epsg",
            self.crs.removeprefix("EPSG:"),
        ]
        base_command.extend(self._get_tool_specific_params())

        # Add possible extra parameters here
        for key, value in (self.extra_lastools_params or {}).items():
            base_command.append(f"-{key}")
            if isinstance(value, (list, tuple)):
                base_command.extend(str(item) for item in value)
            else:
                base_command.append(str(value))
        if Settings.LASTOOLS_DEMO_MODE:
            base_command.append("-demo")
        return base_command

    def _get_tool_specific_params(self) -> list[str]:
        raise NotImplementedError


class Las2DemReader(LASToolsReader):
    """Convert LAS files into DEM raster."""

    # TODO:  use blast2dem64 when bug mentioned in
    #  https://groups.google.com/g/lastools/c/sdD57K4EJKw is fixed
    executable = "/lastools/bin/las2dem_new64"

    def __init__(
        self,
        input_path: pathlib.Path,
        step: int,
        crs: str,  # in format EPSG:xxxx
        keep_class: list[int],
        extra_lastools_params: dict | None = None,
    ) -> None:
        super().__init__(
            input_path=input_path,
            crs=crs,
            extra_lastools_params=extra_lastools_params,
        )
        self.step = step
        self.keep_class = keep_class

    def _get_tool_specific_params(self) -> list[str]:
        return [
            "-step",
            str(self.step),
            "-keep_class",
            *map(str, self.keep_class),
        ]
