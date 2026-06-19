# uc-credentials

A light, reusable credential store. Named login profiles live in a project YAML
file; the rest of the system refers to them by **handle** (name) and never has
to pass secret values around. Passwords are pydantic `SecretStr`, so they redact
themselves in logs, reprs and tracebacks.

Built for two jobs: HTTP **Basic Auth** and normal **form login** — usable both
from an interactive agent (which only ever sees the handle) and from plain
scripts in CI.

## Install

    pip install "uc-credentials @ git+https://github.com/cuber-it/qa-ta-ai-workbench.git#subdirectory=shelf/credentials"

Only depends on `pydantic` and `pyyaml`.

## Store file

A mapping of profile handle to fields (see `credentials.example.yaml`):

```yaml
myapp:
  type: basic
  username: max
  password: s3cret
shop:
  type: form
  url: https://shop.example/login
  username: max@firma.de
  password: hunter2
  user_field: E-Mail
  pass_field: Passwort
  submit: "role=button[name=Login]"
```

Keep it out of version control (`chmod 600`).

## Use

```python
import uc_credentials as creds

creds.set_store_path("/path/to/credentials.yaml")   # or set UC_CREDENTIALS_FILE

creds.list_profiles()             # ['myapp', 'shop']  — names only, safe to show
c = creds.get("shop")             # Credential; repr hides the password
creds.http_credentials("myapp")   # {'username': 'max', 'password': 's3cret'} — injection only
```

## Override per field (CI / scripts)

Environment variables win over the file, so secrets can be injected without
writing them to disk:

    QATAKI_CRED__SHOP__PASSWORD=...
    QATAKI_CRED__SHOP__USERNAME=...

## Growing it

Unknown YAML keys are kept (`extra="allow"`), so profiles can carry more than
the predefined fields without a code change.
