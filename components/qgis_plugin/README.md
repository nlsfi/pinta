# Development of Pinta QGIS plugin

## Setting up development environment

* Make sure you have opened project in devcontainer
* Activate the root venv
* Create a `.env` from `.env.example`, change configurations if needed
* Launch development QGIS: `uv run --all-extras qpdt s` from devcontainer shell

## Translating with QT Linguistic

The translation files are in [i18n](./src/pinta/resources/i18n) folder. Translatable
content in python files is code such as `tr(u"Hello World")`.

Translation files can be updated with `qpdt transup` or wait them to be updated automatically with "update-translations"
pre-commit hook.

After updating ts files, you can open file you wish to translate with Qt Linguist or code editor, make the changes and
compile the translations to .qm files using `qpdt transompile`.
