# Devcontainers

## Host container runtime

Install one of the following on your host:

* Docker
* Podman + podman-docker

The devcontainer image includes `docker` and `docker-compose` CLIs and connects to your host
container engine through a mounted socket.

### Docker

No extra configuration is needed. The default socket path is `/var/run/docker.sock`.

#### Windows using WSL

Development on Windows can be done using devcontainers inside WSL. This requires a WSL distro with Docker
installed (tested with Ubuntu 24.04).

See instructions to:

* [Install Docker on WSL](https://dev.to/0xkoji/setting-up-docker-on-wsl2-with-ubuntu-2404-an-easy-guide-59cd)

### Podman (rootless)

Before opening the devcontainer, set the host socket path:

```bash
export CONTAINER_ENGINE_SOCKET="${XDG_RUNTIME_DIR}/podman/podman.sock"
```

Then start/reopen the devcontainer from the same shell/session.

## IDE configuration

### VSCode

Follow [instructions](https://code.visualstudio.com/docs/remote/wsl) to setup VSCode to use WSL.

Add VSCode settings:

```json
{
    "dev.containers.executeInWSL": true,
    "dev.containers.dockerPath": "docker"
}
```

Open project in devcontainers: Ctrl+Shift+P > Dev Containers: Reopen in container and select WSL (or x11 if developing
from linux) from the list.

### Idea

Setup the following advanced settings: Settings > Advanced Settings

* Open WSL projects natively as local projects
* Open devcontainer project natively

### WSL

* File -> Remote Development -> Start remote development using WSL
* In the new opened windows start remote development using Dev Container and select WSL devcontainer file.

### Linux

Just start remote development using Dev Container and select WSL devcontainer file.
