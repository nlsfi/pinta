# Pinta backend

## Development

By default, run the backend in a container from the repository root with Docker
Compose:

```bash
docker compose up -d
```

The backend listens on `http://localhost:3011` by default and runs with uvicorn
live reload enabled. Override the host port with `COMPOSE_BACKEND_PORT`:

Verify that the API works:

```bash
curl http://localhost:3011/health
```

or play with the API manually with [requests.http](requests.http) file.

### Local development

Optionally run the backend directly on the host from the repository root:

```bash
make backend-start
```

This stops the Compose backend container first, so the local process can bind to
port 3011. From this directory, the equivalent local command is
`python -m pinta_backend`.

## Swagger

FastAPI serves the interactive Openapi spec at
`http://localhost:3011/docs`.

## Building the container

Build targets:

| Target | Package source | Usage |
| --- | --- | --- |
| `dev` | Local repository source | Used by Docker Compose for backend development. Tagged as latest and build from main branch. |
| `prod` | Published PyPI package | Used for release images. Build requires `PINTA_BACKEND_VERSION` and `PINTA_BACKEND_CONSTRAINT`. |

Build a production image with:

```bash
docker build \
  --target prod \
  -f components/backend/Containerfile \
  --build-arg PINTA_BACKEND_VERSION=0.0.0 \
  --build-arg PINTA_BACKEND_CONSTRAINT=https://example.invalid/constraints.txt \
  --build-arg PYPI_INDEX_URL=https://pypi.example.invalid/simple \
  -t ghcr.io/nlsfi/pinta/backend:0.0.0 \
  .
```

Image tags:

* `latest` is the nightly build from the `main` branch.
* Version tags are release builds from tagged versions.

## Translations

The API is localized using the `Accept-Language` request header. The response language is defined in the `Content-Language` response header.

Translate texts with:

```python
from pinta_backend.i18n import _

translated_string = _("Foo")
```

Currently, translations are not automatically updated if the translator is imported using a symbol other than `_`.

### Updating translations

* Update translation files from the repository root with `make backend-ts`, or from this directory with `./src/pinta_backend/scripts/update-translations.sh`
* Update translations in the language-specific `.po` files
* Compile translations from the repository root with `make backend-tc`, or from this directory with `./src/pinta_backend/scripts/compile-translations.sh`

Initialize new languages with:

```bash
msginit --input=<path to .pot> --locale=<locale code> --output-file=<path to output .po>
```
