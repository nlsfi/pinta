# Pinta

> [!CAUTION]
> Under active development!

## Development environment

* Open project in devcontainer, see [instructions](.devcontainer/README.md)
* Activate virtual environment: `source .venv/bin/activate`

Now all dependencies and Git hooks are automatically installed in your virtual environment when using Dev Containers. See the instructions for developing individual components in their respective README files.

### Updating dependencies

`uv lock --upgrade`

## Development instructions

Check [component](./components) related instructions in each component's README.md.

### Commit messages

Commit messages should follow [Conventional Commits notation](https://www.conventionalcommits.org/en/v1.0.0/#summary).

## License

This repository contains multiple components licensed under different licenses.
Unless otherwise noted, source code is licensed under the MIT license.
Exceptions:

* components/qgis_plugin/ - licensed under GPLv3
