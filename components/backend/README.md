# Pinta backend

Run the backend locally from the repository root with `make backend-start`, or from this directory with `python -m pinta_backend`:

Verify that the API works:

```bash
curl http://localhost:3011/health
```

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
