# Pinta

> [!CAUTION]
> Under active development!

## Development environment

* Copy .env.example to .env and adjust settings
* Open project in devcontainer, see [instructions](.devcontainer/README.md)
* Optional: save LASTools license as ./external/LAStools/lastoolslicense.txt
* Activate virtual environment: `source .venv/bin/activate`
* Create a `.env` from `.env.example` and fill empty values and modify configurations if necessary
* Start the containers downloaded from GitHub container registry: `make restart-fully`

Alternatively, you can build the containers from scratch:

* Build all containers: `make build`
* Start the containers: `make up`

Now all development tools and Git hooks are automatically installed in your virtual environment when using Dev
Containers.

### Developing individual components

This project uses [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) and shares just one python
virtual environment
and one single uv.lock file across all components. When developing individual components, go to the component directory
and run `make sync` to synchronize dependencies. Alternatively you can sync component dependencies in root using
`uv sync --package <component-package>`. If component happens to have extras that you want, just add `--all-extras` to
sync command. This will install all the dependencies component's dependencies into venv
and at the same time removes all the libraries that are not needed by that individual component.

If you need to have some other component as a dependency, just run `uv add ../component_name` and uv automatically
updates the component's pyproject.toml file.

See the additional instructions for developing individual components in their respective README files.

### Updating dependencies

If you make any changes to some of the pyproject.toml files, synchronize dependencies with

* Synchronize dependencies: `make sync`

If you want to update locked package versions, run:
`uv lock --upgrade`

## Development instructions

Check [component](./components) related instructions in each component's README.md.

### Commit messages

Commit messages should follow [Conventional Commits notation](https://www.conventionalcommits.org/en/v1.0.0/#summary).

Commit messages are used by [Python Semantic Release (PSR)](https://python-semantic-release.readthedocs.io)
to generate and update component-specific changelogs. By default, PSR can detect which commits are
related to which component by update file path. However, you can specifically define when the commit is relevant to the
package using commit scope that equals the component directory name:

```shell
git commit -m "fix(db): fix something somewhere not in directly componen's path".
```

To trigger a major release for the component, the commit message body must contain a paragraph that begins with
"BREAKING CHANGE:".

### Imports

Imports should follow the [Google style guide](https://google.github.io/styleguide/pyguide.html#22-imports) except for
classes and airflow sdk. Classes could be imported directly
from the module as well as airflow sdk components.

## Release steps

Component releases are automatized with [Python Semantic Release (PSR)](https://python-semantic-release.readthedocs.io).

When the branch is in a releasable state, trigger the `[release.yml](.github/workflows/release.yml)` workflow from
GitHub Actions. Workflow checks which components need releasing automatically based on commits in the repository.
For each component the tag will be created, and a new version to PyPI will be published.

## License

This repository contains multiple components licensed under different licenses.
Unless otherwise noted, source code is licensed under the MIT license.
Exceptions:

* components/qgis_plugin/ - licensed under GPLv3

### Test data license

The database container contains data from the National Land Survey of Finland [Topographic Database](https://www.maanmittauslaitos.fi/en/maps-and-spatial-data/datasets-and-interfaces/product-descriptions/elevation-model-2-m) (04/2026).

Test data under [test_data/point_clouds](/test_data/point_clouds) is licensed under [CC 4.0](https://www.maanmittauslaitos.fi/en/opendata-licence-cc40). The data is based on point clouds with a density of 0.5 points/m² provided by the National Land Survey of Finland. The data has been further thinned.
