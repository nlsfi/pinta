# Pinta

> [!CAUTION]
> Under active development!

## Development environment

* Copy .env.example to .env and adjust settings
* Open project in devcontainer, see [instructions](.devcontainer/README.md)
* Activate virtual environment: `source .venv/bin/activate`

Now all dependencies and Git hooks are automatically installed in your virtual environment when using Dev Containers.
See the instructions for developing individual components in their respective README files.

### Development infra

* Install docker and docker-compose (or podman and podman-docker)
* Build containers with `docker-compose --profile ansible build` or `make build`
* Initialize infra with `docker-compose run --rm ansible` or `make infra-full`
* Run all tests with: `uv run pytest` or `make test`

### Updating dependencies

`uv lock --upgrade`

## Development instructions

Check [component](./components) related instructions in each component's README.md.

### Commit messages

Commit messages should follow [Conventional Commits notation](https://www.conventionalcommits.org/en/v1.0.0/#summary).

## Adapting to a different environment

The ansible infra in this repository is meant to be lightweight and adaptible to any (linux) envrionment.
Therefore, none of the dependencies are installed in playbooks. Instead they are pre-installed in the ansible container.

If you want to use the ansible playbooks to deploy the infra to your own environment,
check the  the dependencies listed in [ansible Containerfile](./infra/containers/ansible/Containerfile)
in SERVER DEPENDENCIES. Make sure to install those to your server first
preferably via separate playbook and provide your own inventories.

## License

This repository contains multiple components licensed under different licenses.
Unless otherwise noted, source code is licensed under the MIT license.
Exceptions:

* components/qgis_plugin/ - licensed under GPLv3
