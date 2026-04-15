## 1. ASGI Entrypoint

- [x] 1.1 Add a dedicated ASGI application module that wraps the existing Flask app with `WsgiToAsgi`
- [x] 1.2 Keep the current Flask app factory as the single source of app configuration and route registration
- [x] 1.3 Ensure local and production startup paths clearly distinguish WSGI dev usage from ASGI deployment usage

## 2. Deployment Runtime

- [x] 2.1 Add the required ASGI server dependency and remove the production dependency on Gunicorn `gthread`
- [x] 2.2 Update `Procfile` to start the ASGI application with Uvicorn
- [x] 2.3 Update `Dockerfile` and any related startup configuration to use the ASGI entrypoint and server command
- [x] 2.4 Document the canonical production startup target so deployment configuration is consistent across environments

## 3. Async Resource Safety

- [x] 3.1 Audit loop-bound async resources that currently assume WSGI request-scoped event loops
- [x] 3.2 Refactor shared async HTTP session management to follow the ASGI worker lifecycle safely
- [x] 3.3 Refactor or replace async cache usage that can reuse loop-bound futures across requests
- [x] 3.4 Verify affected endpoints no longer fail with `Future attached to a different loop`

## 4. Contract Verification

- [x] 4.1 Verify existing routes, methods, and authentication behavior remain unchanged under ASGI
- [x] 4.2 Verify representative JSON responses remain compatible with the current API contract
- [x] 4.3 Run targeted tests or add focused coverage for the ASGI runtime path and async resource behavior

## 5. Rollout

- [x] 5.1 Define an initial ASGI worker/process configuration for production rollout
- [x] 5.2 Keep a documented rollback path to the previous Gunicorn command during cutover
- [x] 5.3 Validate staging or production monitoring for loop errors, memory pressure, and request latency after deployment
