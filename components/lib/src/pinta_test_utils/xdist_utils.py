# Copyright (c) 2026 National Land Survey of Finland
# (https://www.maanmittauslaitos.fi/en).
# This file is part of the Pinta.
# Licensed under the MIT License; see the repository LICENSE file.

import pytest


def _get_optimal_worker_number_for_pytest_xdist(config: pytest.Config) -> int:
    cpu_count = _get_available_cpu_count(config)
    if config.option.maxprocesses:
        cpu_count = min(cpu_count, config.option.maxprocesses)
    return cpu_count


def _get_available_cpu_count(config: pytest.Config) -> int:
    try:
        import psutil  # noqa: PLC0415
    except ImportError:
        pass
    else:
        use_logical = config.option.numprocesses == "logical"
        count = psutil.cpu_count(logical=use_logical) or psutil.cpu_count()
        if count:
            return count
    try:
        from os import sched_getaffinity  # noqa: PLC0415

        def cpu_count() -> int:
            return len(sched_getaffinity(0))

    except ImportError:
        try:
            from os import cpu_count  # type: ignore[assignment]  # noqa: PLC0415
        except ImportError:
            from multiprocessing import cpu_count  # noqa: PLC0415
    try:
        n = cpu_count()
    except NotImplementedError:
        return 1
    return n or 1


@pytest.hookimpl
def get_number_of_workers(config: "pytest.Config") -> int:
    """Determine how many workers to use when running tests.

    This hook is called only if using -n auto.

    If number of workers is zero, debugging works.
    To enable debugging when running multiple tests,
    comment out line "addopts = ..." in pytest.ini.
    """
    invocation_string = config.invocation_params.args[0]
    # Running single test
    if "::" in invocation_string:
        return 0
    return _get_optimal_worker_number_for_pytest_xdist(config)
