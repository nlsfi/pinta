#!/bin/bash

cd src/pinta_qgis_plugin/resources/i18n
for file in *.ts; do
    echo "Compiling $file"
    lrelease "$file"
done

echo "Done."
