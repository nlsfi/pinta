# Development of Pinta QGIS plugin

## Setting up development environment

* Make sure you have opened project in devcontainer
* Activate the root venv
* Create a `.env` from `.env.example`, change configurations if needed
* Launch development QGIS: `qpdt s` from devcontainer shell

## Translating with QT Linguistic

The translation files are in [i18n](./src/pinta/resources/i18n) folder. Translatable
content in python files is code such as `tr(u"Hello World")`.

Translation files can be updated with [updte_translations.sh](./update_translations.sh) script. After updating ts files, you can open file you wish to translate with Qt Linguist or code editor, make the changes and compile the translations to .qm files using [compile_translations.sh](./compile_translations.sh) script.
