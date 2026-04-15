## Why

The API currently runs Flask async routes under Gunicorn `gthread` on WSGI, which creates a poor fit for loop-bound async resources and has already produced cross-loop runtime failures in production. Moving this service to ASGI now is the lowest-risk way to stabilize async behavior, preserve the existing API surface, and avoid a larger framework rewrite.

## What Changes

- Replace the current WSGI Gunicorn `gthread` production runtime with an ASGI-compatible deployment path for the existing Flask application.
- Add an ASGI entrypoint that serves the current Flask app through `WsgiToAsgi` or an equivalent Flask-supported adapter.
- Define runtime requirements so async request handling uses a persistent ASGI event loop model instead of per-request WSGI loop creation.
- Preserve existing routes, authentication behavior, headers, and JSON response shapes during the migration.
- Establish production expectations for async resource lifecycle under ASGI so HTTP clients, caches, and related async components can operate safely.

## Capabilities

### New Capabilities
- `asgi-serving`: The API can be deployed and run through an ASGI server while preserving the existing Flask application contract and endpoint behavior.

### Modified Capabilities
- None.

## Non-goals

- Rewriting the application to FastAPI, Django, Quart, or another framework.
- Changing public endpoint paths, payload formats, or authentication semantics beyond what is required to preserve current behavior.
- Redesigning business logic for schedule, comparison, player, or park factor calculations.
- Fully optimizing or replacing all synchronous `statsapi` usage in this change.

## Impact

Affected areas include deployment/runtime configuration, application startup and entrypoints, async request execution model, and lifecycle management for async resources such as HTTP sessions and caches. Likely touched files include `Procfile`, `Dockerfile`, `run.py`, `app/__init__.py`, and async client/session plumbing.
