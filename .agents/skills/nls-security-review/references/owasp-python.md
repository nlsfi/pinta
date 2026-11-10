# OWASP Top 10:2025 for Python code

For each category: what to look for in Python, what good looks like, and search hints. The search
hints find candidates; reachability from an entry point decides whether they are findings.

Deeper standards when you need a specific requirement: OWASP ASVS 5.0 (verification requirements),
OWASP API Security Top 10 (for HTTP APIs), CWE Top 25. If the code calls LLMs, also check the
OWASP Top 10 for LLM Applications (prompt injection, insecure output handling, excessive agency).

## Contents

- A01 Broken Access Control (incl. SSRF)
- A02 Security Misconfiguration
- A03 Software Supply Chain Failures → see supply-chain.md
- A04 Cryptographic Failures
- A05 Injection
- A06 Insecure Design
- A07 Authentication Failures
- A08 Software or Data Integrity Failures
- A09 Security Logging and Alerting Failures
- A10 Mishandling of Exceptional Conditions
- Python dangerous API quick list

---

## A01 Broken Access Control (incl. SSRF)

Look for:

- Endpoints without an auth dependency/decorator, especially ones added later than their siblings.
  Compare route lists: if most routes have `Depends(get_current_user)` or `@login_required`, the
  ones that do not need a reason.
- Object-level authorisation (IDOR / BOLA): handler fetches by ID from the request
  (`get(id)`, `filter(id=...)`) without checking the caller owns or may see the object.
- Function-level authorisation: admin operations guarded only by UI hiding or a client-supplied
  role/flag.
- Mass assignment: `Model(**request.json())`, `obj.update(**data)`, Pydantic models that accept
  fields like `is_admin`, `owner_id`, `status` from the client.
- Path traversal: user input into `open()`, `Path() / x`, `os.path.join` (an absolute second
  argument discards the base), `send_file`, `FileResponse`. Good: resolve then check
  `resolved.is_relative_to(base.resolve())`.
- Archive extraction: `tarfile.extractall()` without `filter="data"` (Python 3.12+; default only
  from 3.14), `zipfile.extractall()` with untrusted archives (zip slip, symlinks).
- SSRF: user-controlled URL or host into `requests`/`httpx`/`urllib`/GDAL `/vsicurl/`/WMS
  proxies. Good: allow-list of hosts and schemes, block private/link-local ranges after DNS
  resolution, no redirects to unchecked hosts.
- CORS: `allow_origins=["*"]` combined with `allow_credentials=True`.

Search hints: `Depends(`, `login_required`, `permission`, `.get(`, `extractall`, `os.path.join`,
`send_file`, `FileResponse`, `requests.get(`, `httpx.`, `urlopen`, `CORSMiddleware`.

## A02 Security Misconfiguration

Look for:

- Debug on in deployable config: `DEBUG = True`, `app.run(debug=True)`, Werkzeug debugger
  (remote code execution if reachable), FastAPI exposing tracebacks.
- `SECRET_KEY` hard-coded or with a default fallback (`os.getenv("SECRET_KEY", "dev")`).
- `ALLOWED_HOSTS = ["*"]`, permissive CORS, missing security headers on HTML-serving apps.
- Interactive API docs (`/docs`, `/redoc`, `/openapi.json`) exposed in production when not
  intended.
- TLS verification disabled: `verify=False`, `ssl._create_unverified_context`,
  `CERT_NONE`, `check_hostname = False`, `PYTHONHTTPSVERIFY=0`, `urllib3.disable_warnings`.
- Network calls without timeouts (`requests.get(url)` has no default timeout: resource exhaustion).
- Services binding `0.0.0.0` where localhost is intended.
- Overly broad DB roles, default credentials in config or compose files.
- Default-permissive XML parsers (see A05).

Search hints: `debug=True`, `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `verify=False`, `CERT_NONE`,
`disable_warnings`, `timeout`, `0.0.0.0`, `docs_url`.

## A03 Software Supply Chain Failures

See `supply-chain.md`.

## A04 Cryptographic Failures

Look for:

- `random` module for tokens, passwords, IDs, nonces. Good: `secrets.token_urlsafe()`,
  `secrets.compare_digest()`.
- Password hashing with `hashlib` (MD5, SHA-1, plain SHA-256, even salted). Good: argon2-cffi,
  bcrypt, or `hashlib.scrypt`/PBKDF2 with appropriate parameters via a vetted library.
- MD5/SHA-1 for integrity or signatures (fine for non-security cache keys; flag only security use).
  `hashlib.md5(..., usedforsecurity=False)` documents intent.
- Token/HMAC comparison with `==` (timing attack). Good: `hmac.compare_digest`.
- Home-made crypto, ECB mode, static IVs/nonces, hard-coded keys, PyCrypto (unmaintained) instead
  of `cryptography`.
- JWT: `jwt.decode` without `algorithms=[...]`, `verify_signature: False`, accepting `none`,
  missing `aud`/`iss`/`exp` checks, symmetric secrets that are short or committed.
- Sensitive data in transit over HTTP, or stored unencrypted where policy requires encryption.

Search hints: `import random`, `random.`, `hashlib.md5`, `sha1`, `== token`, `jwt.decode`,
`AES.new`, `MODE_ECB`, `Crypto.`.

## A05 Injection

SQL:

- f-strings, `%`, `.format()` or `+` building SQL passed to `cursor.execute`,
  `session.execute(text(...))`, `engine.execute`, `pd.read_sql`, raw ORM queries.
  Good: bound parameters (`execute(sql, params)`, `text("... :x").bindparams(x=...)`).
- Identifiers (table/column/schema names, ORDER BY direction) cannot be bound as parameters. Good:
  allow-list, or `psycopg.sql.Identifier` / `psycopg2.sql.Identifier`, or SQLAlchemy `column()`
  from a fixed mapping.
- `LIKE` patterns built from input (wildcard injection; usually Low).

OS commands:

- `subprocess.*(..., shell=True)` with any non-constant string, `os.system`, `os.popen`,
  `commands`, `pexpect.spawn(str)`. Good: list arguments, `shell=False`, and `--` before
  user-supplied positional args to prevent option injection (`git`, `tar`, `gdal_translate`).
- `shlex.quote` is a mitigation on POSIX only; it is not correct for `cmd.exe`/PowerShell.

Code execution:

- `eval`, `exec`, `compile`, `__import__`/`importlib.import_module` with input, `pickle`/
  `cPickle`/`dill`/`shelve`/`jsonpickle`/`marshal` loads of untrusted data, `yaml.load` without
  `SafeLoader` (use `yaml.safe_load`), `joblib.load`, `numpy.load(allow_pickle=True)`,
  `torch.load` without `weights_only=True`, `pandas.read_pickle`.
- `ast.literal_eval` is safe from code execution but can exhaust memory on huge input.

Templates and output:

- Jinja2 `Environment()` without `autoescape=select_autoescape()` for HTML; `Markup(user)`,
  `|safe` on user data; `render_template_string` with user input (server-side template
  injection, often code execution).
- Building HTML by string concatenation; returning user input in `HTMLResponse`.

XML:

- `xml.etree`, `xml.dom.minidom`, `xml.sax`, `lxml.etree` on untrusted XML. Risks: entity
  expansion (billion laughs), XXE (lxml, older parsers), network fetches. Good: `defusedxml`, or
  `lxml.etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)`.

Other:

- LDAP filters built by concatenation; header injection (CRLF in values passed to response
  headers or email headers); log injection (newlines in logged user input, see A09).
- Regular expressions with nested quantifiers applied to user input (ReDoS). Python's `re` has
  no timeout; prefer bounded patterns or input length limits.
- `str.format` with user-controlled format strings (`user_fmt.format(obj=...)` can read
  attributes such as `{obj.__init__.__globals__}`).

Search hints: `execute(`, `text(`, `f"SELECT`, `f"INSERT`, `f"UPDATE`, `f"DELETE`, `.format(`,
`shell=True`, `os.system`, `eval(`, `exec(`, `pickle`, `yaml.load`, `allow_pickle`,
`torch.load`, `render_template_string`, `autoescape`, `etree`, `minidom`, `re.compile`.

## A06 Insecure Design

Tools cannot find these; reason about them from the threat model.

- Business rules enforced only client-side (QGIS plugin, front end) but not in the API.
- Missing rate limiting or resource limits on expensive operations: spatial queries over the whole
  country, raster processing, report generation, file uploads without size limits.
- Workflows that can be skipped or replayed (state machine without server-side state checks).
- Trusting data because it comes from "our own" system that untrusted users can also write to.
- Batch jobs that run with far more privilege than they need.

## A07 Authentication Failures

- Hand-rolled login/session handling where the framework provides one.
- Credentials in code, config, notebooks or tests (also see secrets in
  `cicd-secrets-containers.md`).
- Session tokens without expiry; logout that does not invalidate server-side state.
- OAuth/OIDC: missing `state`/PKCE, not validating ID token signature/audience/issuer,
  open redirects in `redirect_uri` handling.
- Basic auth over HTTP; API keys in query strings (end up in logs).
- No lockout or throttling on credential checks.
- Service-to-service calls without authentication on an assumed-trusted internal network.

## A08 Software or Data Integrity Failures

- Deserialising untrusted data (see A05 code execution).
- Downloading and executing or loading code, models, plugins or scripts without signature/hash
  verification (`requests.get(url).text` → `exec`, auto-updaters, plugin loaders).
- Accepting signed data without verifying the signature (webhooks without HMAC checks, JWT
  without verification).
- Caches or shared directories that untrusted parties can write and the app later loads from.
- CI/CD integrity issues: see `cicd-secrets-containers.md`.

## A09 Security Logging and Alerting Failures

- Security-relevant events not logged: failed logins, authorisation denials, admin actions,
  input validation failures on sensitive endpoints.
- Sensitive data logged: passwords, tokens, full request bodies with personal data, connection
  strings (`logger.info(f"connecting {dsn}")`), `repr()` of objects holding secrets.
- Log injection: user input logged without neutralising newlines (forged log lines).
- `print` instead of logging in services; exceptions swallowed without logging.

## A10 Mishandling of Exceptional Conditions

- Fail-open: `try: check_permission() except Exception: pass` or returning `True` on error.
- Bare `except:` / `except Exception:` around security checks, transactions or validation.
- Leaking stack traces, SQL, file paths or library versions in error responses.
- Partial failure leaving inconsistent state (no transaction or rollback around multi-step writes).
- Missing handling for resource exhaustion: huge inputs, deep recursion, decompression bombs,
  timeouts not set or not handled.
- `assert` used for security or input checks (removed with `python -O`).
- Errors converted to defaults that change meaning (`int(x) if x else 0` making "missing" mean
  "unlimited" or "admin").

Search hints: `except:`, `except Exception`, `pass`, `assert`, `traceback`, `return True`.

---

## Python dangerous API quick list

| API | Risk | Safer alternative |
| --- | --- | --- |
| `eval`, `exec`, `compile` on input | Code execution | Parse explicitly; `ast.literal_eval` for literals |
| `pickle`, `dill`, `shelve`, `jsonpickle`, `marshal` | Code execution | JSON, msgpack with schema |
| `yaml.load` (non-safe loader) | Code execution | `yaml.safe_load` |
| `numpy.load(allow_pickle=True)`, `torch.load`, `joblib.load` | Code execution | `allow_pickle=False`, `weights_only=True`, trusted sources only |
| `subprocess(..., shell=True)`, `os.system`, `os.popen` | Command injection | List args, `shell=False` |
| `tarfile.extractall()` | Path traversal | `extractall(filter="data")` |
| `zipfile.extractall()` | Zip slip, bombs | Validate member names and sizes |
| `xml.*`, `lxml` defaults | XXE, entity expansion | `defusedxml`, hardened lxml parser |
| `tempfile.mktemp` | Race condition | `NamedTemporaryFile`, `mkstemp` |
| `random` for secrets | Predictable tokens | `secrets` |
| `hashlib.md5/sha1` for passwords | Weak hashing | argon2/bcrypt/scrypt |
| `requests(..., verify=False)` | MITM | Fix the CA bundle (`REQUESTS_CA_BUNDLE`) |
| `requests` without `timeout` | Resource exhaustion | Always set `timeout` |
| `jinja2.Environment()` | XSS | `autoescape=select_autoescape()` |
| `render_template_string(user)` | SSTI | Never template user input |
| `jwt.decode` without `algorithms` | Auth bypass | Explicit algorithms, verify claims |
| `assert` for checks | Removed with `-O` | Explicit `if ...: raise` |
| `os.chmod(..., 0o777)`, world-writable files | Tampering | Least privilege modes |
