# Devcontainers

## Windows using WSL

Development on Windows can be done using devcontainers inside WSL. This requires a WSL distro with Docker installed (tested with Ubuntu 24.04).

See instructions to:

* [Install Docker on WSL](https://dev.to/0xkoji/setting-up-docker-on-wsl2-with-ubuntu-2404-an-easy-guide-59cd)

### VSCode

Follow [instructions](https://code.visualstudio.com/docs/remote/wsl) to setup VSCode to use WSL.

Add VSCode settings:

```json
{
    "dev.containers.executeInWSL": true,
    "dev.containers.dockerPath": "docker"
}
```

Open project in devcontainers: Ctrl+Shift+P > Dev Containers: Reopen in container and select WSL from the list.

### Idea

TODO

## Linux

TODO
