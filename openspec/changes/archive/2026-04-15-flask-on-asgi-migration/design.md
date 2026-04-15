## Context

The current API is a Flask application with multiple `async def` routes, but production serves it through Gunicorn `gthread` under WSGI. That runtime model creates request-scoped event loops and has already surfaced loop-affinity failures in production for async caches and HTTP session management. The goal of this change is to stabilize async execution without rewriting the application into a new framework or changing the public API.

## Goals / Non-Goals

**Goals:**
- Run the existing Flask app behind an ASGI server instead of Gunicorn `gthread`.
- Preserve current routes, authentication hooks, response shapes, and blueprint structure.
- Provide a stable async execution model so loop-bound resources can be managed safely.
- Keep the deployment change small enough to roll out and rollback cleanly.

**Non-Goals:**
- Rewriting the app to FastAPI, Django, or Quart.
- Reworking business logic in schedule, player, comparison, or park factor services.
- Eliminating all synchronous `statsapi` calls in this migration.
- Introducing a distributed cache or redesigning rate limiting storage.

## Decisions

### Use Flask with an ASGI adapter instead of a framework rewrite
The application SHALL remain a Flask app and be served through Flask's supported ASGI path using `WsgiToAsgi` or an equivalent adapter. This removes the WSGI/request-loop mismatch while preserving the current app factory, blueprints, and middleware-style hooks.

Alternatives considered:
- FastAPI: better long-term async ergonomics, but unnecessary rewrite cost for the current stabilization goal.
- Quart: closer to Flask than FastAPI, but still larger migration surface than needed.

### Move to a native ASGI server and retire Gunicorn `gthread`
Production SHALL use a native ASGI server, with Uvicorn as the default target. This simplifies the runtime model, avoids the current threaded WSGI setup, and aligns deployment with the app's async routes.

Alternatives considered:
- Keep Gunicorn and swap worker class: does not address the core mismatch as cleanly as moving to ASGI directly.
- Hypercorn: acceptable alternative, but Uvicorn has the narrower operational surface for this service.

### Add a dedicated ASGI entrypoint
The repo SHALL expose a dedicated ASGI module that wraps the existing Flask app factory. This isolates deployment concerns from `run.py`, keeps local/dev startup understandable, and gives the platform one canonical ASGI target.

Alternatives considered:
- Reusing `run.py`: couples dev and production runtime concerns and makes rollback/migration harder to reason about.

### Preserve the public API contract during the migration
The migration SHALL keep the same routes, methods, authentication behavior, and JSON payload contracts. Runtime changes are allowed; externally visible API changes are not.

Alternatives considered:
- Opportunistic API cleanup during migration: rejected because it mixes stabilization with behavior change and makes rollback harder.

### Rebind async resource lifecycle to the ASGI worker model
Async HTTP sessions and async caches SHALL be reviewed and updated to match long-lived ASGI worker event loops rather than WSGI request-scoped loops. This is necessary to remove the current cross-loop failure mode and avoid recreating it under a different server command.

Alternatives considered:
- Only changing the server command: insufficient because existing loop-bound resource patterns still need to be validated against the new lifecycle.

## Risks / Trade-offs

- [ASGI server behavior differs from current deployment] → Validate startup, shutdown, health checks, headers, and signal handling in staging before cutover.
- [Some code paths still rely on `asyncio.to_thread` around sync libraries] → Accept reduced benefit in those paths for now; keep this migration focused on runtime correctness first.
- [Per-process memory caches and in-memory rate limiting remain local to each worker] → Preserve current behavior for now and document that horizontal consistency is out of scope for this change.
- [Rollback may be needed quickly if platform-specific issues appear] → Keep the prior Gunicorn command available as a temporary rollback path until ASGI production confidence is established.

## Migration Plan

1. Add an ASGI entrypoint for the current Flask app.
2. Update deployment configuration to launch the ASGI app with Uvicorn.
3. Adjust async resource lifecycle where current code assumes WSGI request-local loops.
4. Verify existing endpoints and auth behavior remain unchanged.
5. Deploy behind the new runtime and monitor for loop errors, memory pressure, and request latency.
6. Retain the previous Gunicorn command as a rollback option during initial rollout.

## Open Questions

- Whether the production platform should run one or multiple ASGI worker processes initially.
- Whether any startup/shutdown hooks are needed beyond the ASGI adapter for async client cleanup.
- Whether Hypercorn should remain a documented fallback if Uvicorn exposes platform-specific issues.
