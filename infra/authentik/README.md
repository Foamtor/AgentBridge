# Authentik (optional)

Local smoke does **not** require Authentik. Default API runs with `AUTH_REQUIRED=false`.

## Start (optional)

```bash
docker compose --profile auth up -d
```

Then set in `.env`:

```text
AUTH_REQUIRED=true
OIDC_ISSUER=http://localhost:9000/application/o/<app>/
OIDC_AUDIENCE=<client-id>
```

Configure an OAuth2/OIDC provider in Authentik UI and point the React debug console
at the issuer / client id. Full production hardening is out of scope for template smoke.
