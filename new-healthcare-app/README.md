# Deploying with Kong as a real API gateway

## Using your existing database, not a new one

This compose file deliberately has no `postgres`/`pgadmin` services — it connects
to your **existing** `kidney_cardiology_db` container instead of creating a second
one. `docker compose ps` will show 3 containers now (`backend`, `frontend`, `kong`),
not 5 — that's correct, not a sign something failed to start. Keep your existing
db container running exactly as it is; nothing here manages its lifecycle, starts
it, or stops it.

## What changed from the nginx version

nginx now only serves the static frontend build — it no longer proxies `/api/`.
**Kong is the new single entry point** for everything: the page itself, `/api/v1/*`,
and `/health`. That's the one URL you share with your boss (port 8080).

Three real gateway features, not just routing:

- **Versioning**: the public URL is `/api/v1/...`. Kong strips `/v1` and forwards to
  the backend's real (currently single) `/api/...` routes. This prepares the URL
  structure for a future `/api/v2` — it does not mean two different backend
  behaviors exist today, and I want to be direct about that rather than overclaim it.
- **Rate limiting**: 60 requests/minute per client, enforced at the gateway before
  a request ever reaches the backend.
- **Authentication**: Kong validates a real Auth0-issued JWT on every `/api/v1/*`
  request. This is a genuine security upgrade worth knowing about directly: **the
  backend API had no authentication enforcement at all before this** — login only
  ever gated the UI, not the API itself. Anyone who could reach the backend's port
  directly could call it with zero credentials. That gap is now closed at the
  gateway. The backend itself still doesn't independently verify tokens — Kong is
  currently the only layer doing it. Real defense-in-depth would have the backend
  verify too; that's real, separate follow-up work, not done here.

## 1. One-time Auth0 setup

### Create an API resource (if you haven't already)

In your Auth0 dashboard: **Applications -> APIs -> Create API**. The **Identifier**
you set here (a URL-shaped string, doesn't have to resolve to anything real) is
your `VITE_AUTH0_AUDIENCE` value. Without this, Auth0 issues an opaque token
instead of a real JWT, and Kong's `jwt` plugin has nothing it can validate.

### Get your tenant's public key

```bash
curl https://YOUR_TENANT.us.auth0.com/pem -o auth0-cert.pem
openssl x509 -in auth0-cert.pem -pubkey -noout > auth0-public-key.pem
cat auth0-public-key.pem
```

Paste the full output (including the `-----BEGIN PUBLIC KEY-----` /
`-----END PUBLIC KEY-----` lines) into `kong/kong.yml`, replacing the placeholder
under `rsa_public_key`.

### Get the exact issuer value

Log into the running app once, open browser DevTools -> Network tab, find any
`/api/v1/...` request, and look at its `Authorization: Bearer ...` header. Paste
just the token part into jwt.io (decoding locally in your browser — nothing is
sent anywhere) and read the `iss` claim. Paste that **exact** string, including
the trailing slash, into `kong.yml`'s consumer `key` field, replacing
`https://YOUR_AUTH0_DOMAIN/`.

## 2. Place the files

Same as before, plus a new `kong/` folder:

```
your-project/
  docker-compose.yml
  kong/
    kong.yml
  .env
  backend_folder/  (Dockerfile, .dockerignore — unchanged from before)
  frontend_folder/ (Dockerfile, nginx.conf — nginx.conf changed, see above)
```

## 3. Build and start

```powershell
docker compose down
docker compose up -d --build
```

## 4. Migrations and seed (one time, same as before)

```powershell
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed
```

## 5. Test each gateway feature before sharing anything

**Versioning** — this should work:
```powershell
curl http://localhost:8080/api/v1/patients
```
This should fail (Kong doesn't know this path at all — direct backend access no
longer exists from outside Docker):
```powershell
curl http://localhost:8080/api/patients
```

**Authentication** — without a token, this should return `401`:
```powershell
curl -i http://localhost:8080/api/v1/patients
```
The real app (with a logged-in session) should work normally — open
`http://localhost:8080` in a browser and log in as usual.

**Rate limiting** — after around 60 requests within a minute, you should start
seeing `429 Too Many Requests` on authenticated `/api/v1/*` calls. The simplest way
to see this: log in through the browser and rapidly refresh a patient's assessment
list several dozen times, or script repeated authenticated calls with a real
Bearer token. `/health` is deliberately not rate-limited, so testing against it
won't demonstrate this.

## 6. Share the URL

Same as before — `ngrok http 8080` now points at Kong instead of directly at the
frontend, but the workflow is identical. **The Auth0 dashboard step (adding the
shared URL to Allowed Callback/Logout/Web Origin URLs) is still required and still
gets missed if you skip it.**

## Known limitation worth knowing about

Kong's open-source `jwt` plugin validates against a **manually registered** public
key — it does not automatically fetch or rotate keys from Auth0's JWKS endpoint the
way a full OIDC integration would. Auth0 rotates signing keys infrequently, but if
it ever does, requests will start failing with signature-verification errors until
you repeat the "get your tenant's public key" step above and redeploy. Kong
Enterprise's OpenID Connect plugin handles this automatically; that's a licensing
decision, not something to patch around in the OSS config.

## Troubleshooting

**Every request returns 401, even with a valid login**: almost always the `iss`
value in `kong.yml` not exactly matching your real token's issuer, or the public
key being pasted with the wrong line endings/wrapper. Decode a real token at
jwt.io and compare its `iss` character-for-character against `kong.yml`.

**Kong container won't start**: check `docker compose logs kong` — a malformed
`kong.yml` (bad YAML indentation, a missing `|` before a multi-line PEM block) is
the most common cause, and Kong's error message usually names the exact line.
