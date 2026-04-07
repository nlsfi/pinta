# Pinta QGIS plugin component

## Providing custom basemaps

It is possible to provide custom basemaps for Pinta QGIS plugin. Just copy the
default [basemap_layer_config.json](src/pinta_qgis_plugin/resources/layer_config/basemap_layer_config.json) and modify
it to add your own basemaps. Currently XYZ, WMS and WMTS basemaps are supported.

Here is an example of a basemap layer config:

```json
[
    {
    "layer_name": "OpenStreetMap",
    "uri_parameters": {
      "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      "type": "xyz"
    }
  },
  {
    "layer_name": "Your own basemap",
    "uri_parameters": {
      "url": "https://your-wmts-service/wmts/1.0.0/WMTSCapabilities.xml",
      "crs": "EPSG:3067",
      "layers": "layername",
      "tileMatrixSet": "ETRS-TM35FIN",
      "styles": "default"
    }
  }
]

```

## Development environment

### Setting up development environment

* Make sure you have opened project in devcontainer and have setup the environment and infra
* Launch development QGIS: `uv run --all-extras qpdt s` from devcontainer shell in this directory or `make qgis-start`
  in project root

### Translating with QT Linguistic

The translation files are in [i18n](./src/pinta/resources/i18n) folder. Translatable
content in python files is code such as `tr(u"Hello World")`.

Translation files can be updated with `qpdt transup` or wait them to be updated automatically with "update-translations"
pre-commit hook.

After updating ts files, you can open file you wish to translate with Qt Linguist or code editor, make the changes and
compile the translations to .qm files using `qpdt transompile`.
