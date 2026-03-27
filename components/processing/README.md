# Processing component

Running Python code from processing component:

* Build the container in project root: `docker-compose build processing`
* Run code: `docker-compose run --rm processing python -m pinta_processing.main` or `docker-compose run --rm processing python src/pinta_processing/main.py`

## Pipelines

The processing component provides a pipeline architecture for chaining raster and vector data processing operations together.

### Core Concepts

**Pipeline**: A chain of processing stages that execute sequentially. Each stage processes raster or vector data and passes the result to the next stage or returns the data as pipeline output.

**Stage**: A processing operation that implements the `process(data)` method. Stages receive a `RasterDataset` or `VectorDataset` (or `None`), perform an operation, and return the result.

**RasterDataset**: A container for raster data consisting of:

* `array`: NumPy array containing the raster values
* `transform`: Affine transformation for georeferencing
* `crs`: Coordinate Reference System
* `nodata`: Nodata value

### Creating Pipelines

Pipelines are created using the pipe operator (`|`) to chain stages together:

```python
from pinta_processing import reader, writer, filter

# Simple read-transform-write pipeline
pipeline = reader.RasterioReader("input.tif") \
    | filter.MultiplyValues(factor=2.0) \
    | writer.GeotiffWriter("output.tif")

# Execute pipeline (read-only stages like reader return data)
pipeline.execute()
```

Example of pipeline returning raster data:

```python
from pinta_processing import reader, writer, filter

# Simple read-transform-write pipeline
pipeline = reader.RasterioReader("input.tif") \
    | filter.MultiplyValues(factor=2.0)

# Execute pipeline (read-only stages like reader return data)
result = pipeline.execute()
# Get raster pixels as np array
result.array
```

### Pipeline Modules

#### Reader

The `reader` module handles loading raster or vector data for various sources.

#### Filter

The `filter` module contains data transformation stages that modify data while preserving metadata.

#### Writer

The `writer` module handles saving data to various medias. All writer stages behave as sinks; no data is returned from a writer, and the pipeline branch does not continue after a writer stage.

#### Tee

The `Tee` stage branches a pipeline into multiple parallel paths without affecting the main data stream:

```python
from pinta_processing import core, reader, filter, writer

# Create a branching pipeline where data goes to multiple writers
pipeline = (
    reader.RasterioReader("dem.asc")
    | core.Tee(
        filter.MultiplyValues(2.0)
        | writer.GeotiffWriter("dem_multiplied.tif")
    )
    | writer.GeotiffWriter("dem.tif")
)

pipeline.execute()
```

Each branch receives an independent copy of the data, allowing simultaneous write operations without interference. The main data stream continues unchanged after the Tee.
