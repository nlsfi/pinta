#!/bin/bash

cd src
py_files=$(python -c "import glob; print(str(' '.join(list(glob.glob('**/*.ui', recursive=True))) + ' ' + ' '.join(list(glob.glob('**/*.py', recursive=True)))).replace('\\\', '/'))")

python -m PyQt5.pylupdate_main $py_files -ts pinta_qgis_plugin/resources/i18n/fi.ts -noobsolete -verbose
