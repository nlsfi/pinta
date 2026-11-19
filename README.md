# Pinta

> [!CAUTION]
> Under active development!

## About the Pinta project

The National Land Survey of Finland maintains a nationwide terrain model with a resolution of 2 metres. The terrain model is available as open data through viewing and download services: [Elevation model 2 m](https://www.maanmittauslaitos.fi/en/maps-and-spatial-data/datasets-and-interfaces/product-descriptions/elevation-model-2-m)

The current national laser scanning programme produces point clouds captured during the summer season. To maintain the accuracy of the terrain model, it is updated only with changes resulting from construction activities, soil extraction, and other significant terrain modifications. The original terrain model is based on springtime laser scanning data, which is less affected by vegetation.

Pinta enables the creation of a reference terrain model from new point cloud data collected in production areas. It allows users to efficiently identify, review, and approve terrain changes interactively. The system then updates the current terrain model with the accepted changes.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development environment setup and development conventions.

## License

This repository contains multiple components licensed under different licenses.
Unless otherwise noted, source code is licensed under the MIT license.
Exceptions:

* components/qgis_plugin/ - licensed under GPLv3

### Test data license

The database container contains data from the National Land Survey of Finland [Elevation model 2m](https://www.maanmittauslaitos.fi/en/maps-and-spatial-data/datasets-and-interfaces/product-descriptions/elevation-model-2-m) (04/2026).

Test data in [test_data/processing/lake_part.gpkg](/test_data/processing/lake_part.gpkg) contains data from the National Land Survey of Finland [Topographic Database](https://www.maanmittauslaitos.fi/en/maps-and-spatial-data/datasets-and-interfaces/product-descriptions/topographic-database) (08/2026).

Test data under [test_data/point_clouds](/test_data/point_clouds) is licensed under [CC 4.0](https://www.maanmittauslaitos.fi/en/opendata-licence-cc40). The data is based on point clouds with a density of 0.5 points/m² provided by the National Land Survey of Finland. The data has been further thinned.
