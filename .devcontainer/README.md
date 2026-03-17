# Devcontainers

## Host container runtime

Install one of the following on your host:

* Docker
* Podman + podman-docker

The devcontainer image includes `docker` and `docker-compose` CLIs and connects to your host container engine through a
mounted socket.

### Docker

No extra configuration is needed. The default socket path is `/var/run/docker.sock`.

### Podman (rootless)

Before opening the devcontainer, set the host socket path:

```bash
export CONTAINER_ENGINE_SOCKET="${XDG_RUNTIME_DIR}/podman/podman.sock"
```

Then start/reopen the devcontainer from the same shell/session.

## Development in Windows using WSL

Development on Windows can be done using devcontainers inside WSL. This requires a WSL distro with Docker
installed (tested with Ubuntu 24.04).

Follow these steps to setup WSL and Docker:

> [!NOTE]
> If you work behind a corporate proxy, follow the [proxy settings](#proxy-settings) section alongside the steps below.

### Run in Windows Command Prompt / PowerShell

* Update WSL:

  ```powershell
  wsl --update
  ```

* List available Ubuntu distributions:

  ```powershell
  wsl --list --online
  ```

* Install Ubuntu 24.04:

  ```powershell
  wsl --install -d Ubuntu-24.04
  ```

* Set the new distro as the default one:

  ```powershell
  wsl -s Ubuntu-24.04
  ```

### Run in WSL

* Download the get-docker script:

  ```bash
  curl -fsSL https://get.docker.com -o get-docker.sh
  ```

* Modify `get-docker.sh` by replacing `true` in the `is_wsl()` function with `false`
* Install Docker:

  ```bash
  sudo sh get-docker.sh
  ```

* Add yourself to the docker group:

  ```bash
  sudo usermod -aG docker $USER
  ```

* Open a new WSL shell so Docker can be used without `sudo`
* Test the setup:

  ```bash
  docker run --rm hello-world
  ```

* Optional: clone the repository again inside WSL for an extra performance boost

### Proxy settings

If you work behind a corporate proxy, do these steps as well.

#### Before installing Docker

1. Check the DNS server on **Windows**:

   ```powershell
   ipconfig /all
   ```

2. Insert the value into `/etc/resolv.conf` in WSL, for example:

   ```bash
   $ sudo nano /etc/resolv.conf
   nameserver 10.10.10.10
   ```

3. Set up proxy environment variables in `~/.bashrc` in WSL and activate them with `source`:

   ```bash
   $ nano ~/.bashrc
   export HTTP_PROXY=http://USERNAME:PASSWORD@SERVER:PORT
   export HTTPS_PROXY=https://USERNAME:PASSWORD@SERVER:PORT
   export NO_PROXY=localhost,127.0.0.1
   $ source ~/.bashrc
   ```

4. Set up apt proxy environment in WSL in `/etc/apt/apt.conf`:

   ```bash
   $ sudo nano /etc/apt/apt.conf
   Acquire::http::Proxy "http://USERNAME:PASSWORD@SERVER:PORT";
   Acquire::https::Proxy "https://USERNAME:PASSWORD@SERVER:PORT";
   ```

##### After installing docker

1. Set up proxy settings in ~/.docker/config.json

    ```shell
    $ nano ~/.docker/config.json
    {
        "proxies": {
            "default": {
                "httpProxy": "http://USERNAME:PASSWORD@SERVER:PORT",
                "httpsProxy": "https://USERNAME:PASSWORD@SERVER:PORT",
                "noProxy": "localhost,127.0.0.1"
            }
        }
    }
    ```

2. Create directory `sudo mkdir /etc/systemd/system/docker.service.d`
3. Create new file `/etc/systemd/system/docker.service.d/http-proxy.conf` and put the following proxy
   variables:

    ```shell
    [Service]
    Environment="HTTP_PROXY=https://USERNAME:PASSWORD@SERVER:PORT"
    Environment="HTTPS_PROXY=https://USERNAME:PASSWORD@SERVER:PORT"
    Environment="NO_PROXY=localhost,127.0.0.1"
    ```

4. Restart docker daemon with `sudo systemctl daemon-reload` and `sudo systemctl restart docker`

## IDE configuration

### VSCode

Follow [instructions](https://code.visualstudio.com/docs/remote/wsl) to setup VSCode to use WSL.

Install [Dev Containers extension](https://code.visualstudio.com/docs/devcontainers/containers).

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
