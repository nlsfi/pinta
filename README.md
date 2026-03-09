# Pinta

> [!CAUTION]
> Under active development!

## Development environment

* Install [uv](https://docs.astral.sh/uv/getting-started/installation/) globally or optionally later on inside the
  virtual environment
* Create virtual environment: `python -m venv .venv`
* Activate virtual environment: `source .venv/bin/activate` or `.\.venv\Scripts\activate.bat`
* Install dependencies: `uv sync`
  * If not using global uv, install uv first with: `pip install uv`
* Install prek to run pre-commit hooks: `prek install`

### Updating dependencies

`uv lock --upgrade`

## License

This repository contains multiple components licensed under different licenses.
Unless otherwise noted, source code is licensed under the MIT license.
Exceptions:

* components/qgis_plugin/ - licensed under GPLv3
