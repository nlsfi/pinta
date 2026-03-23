# Pinta

> [!CAUTION]
> Under active development!

## Development environment

* Copy .env.example to .env and adjust settings
* Open project in devcontainer, see [instructions](.devcontainer/README.md)
* Activate virtual environment: `source .venv/bin/activate`
* Create a `.env` from `.env.example` and add needed configurations

Now all development tools and Git hooks are automatically installed in your virtual environment when using Dev
Containers.

### Developing individual components

This project uses [uv workspaces](https://docs.astral.sh/uv/concepts/projects/workspaces/) and shares just one python
virtual environment
and one single uv.lock file across all components. When developing individual components, go to the component directory
and run `uv sync` to synchronize dependencies. Alternatively you can sync component dependencies in root using
`uv sync --package <component-package>`. If component happens to have extras that you want, just add `--all-extras` to
sync command. This will install all the dependencies component's dependencies into venv
and at the same time removes all the libraries that are not needed by that individual component.

If you need to have some other component as a dependency, just run `uv add ../component_name` and uv automatically
updates the component's pyproject.toml file.

See the additional instructions for developing individual components in their respective README files.

### Development infra

* Build containers with `docker-compose --profile ansible build` or `make build`
* Initialize infra with `docker-compose run --rm ansible` or `make infra-full`
* Run all tests with: `uv run pytest` or `make test`

### Updating dependencies

If you make any changes to some of the pyproject.toml files, synchronize dependencies with

* Synchronize dependencies: `uv sync --all-packages --all-groups --all-extras --no-extra qgis` or `make sync`

If you want to update locked package versions, run:
`uv lock --upgrade`

## Development instructions

Check [component](./components) related instructions in each component's README.md.

### Commit messages

Commit messages should follow [Conventional Commits notation](https://www.conventionalcommits.org/en/v1.0.0/#summary).

## Adapting to a different environment

The ansible infra in this repository is meant to be lightweight and adaptible to any (linux) envrionment.
Therefore, none of the dependencies are installed in playbooks. Instead they are pre-installed in the ansible container.

If you want to use the ansible playbooks to deploy the infra to your own environment,
check the dependencies listed in [ansible Containerfile](./infra/containers/ansible/Containerfile)
in SERVER DEPENDENCIES. Make sure to install those to your server first
preferably via separate playbook and provide your own inventories.

## License

This repository contains multiple components licensed under different licenses.
Unless otherwise noted, source code is licensed under the MIT license.
Exceptions:

* components/qgis_plugin/ - licensed under GPLv3
