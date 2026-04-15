## Purpose

Define the canonical ASGI deployment requirements for the existing Flask application so production serving, runtime safety, and deployment documentation stay consistent.

## Requirements

### Requirement: Flask application is deployable through ASGI
The system SHALL expose an ASGI-compatible entrypoint for the existing Flask application and SHALL run production traffic through an ASGI server instead of Gunicorn `gthread`.

#### Scenario: ASGI server startup
- **WHEN** the production runtime starts the application
- **THEN** it loads the Flask app through an ASGI-compatible entrypoint
- **AND** it does not start the service with Gunicorn `gthread`

### Requirement: Existing API contract is preserved during ASGI migration
The system SHALL preserve existing HTTP routes, methods, authentication behavior, and JSON response contracts while moving the runtime from WSGI to ASGI.

#### Scenario: Existing endpoint behavior remains available
- **WHEN** a client calls an existing API endpoint after the ASGI migration
- **THEN** the route path and HTTP method remain valid
- **AND** the response schema remains compatible with the pre-migration API contract

### Requirement: Async resources operate safely across requests under ASGI
The system SHALL manage async HTTP sessions, caches, and related loop-bound resources in a way that is valid for the ASGI worker lifecycle and does not depend on WSGI request-scoped event loops.

#### Scenario: Repeated async requests reuse safe async state
- **WHEN** multiple requests hit endpoints that use cached async data or shared async HTTP clients
- **THEN** the requests complete without `Future attached to a different loop` runtime failures
- **AND** async resource reuse follows the ASGI worker lifecycle

### Requirement: Deployment configuration documents the ASGI runtime
The system SHALL define a single production deployment path for ASGI serving so local operators and the hosting platform use the same runtime target.

#### Scenario: Deployment configuration points to ASGI target
- **WHEN** an operator reviews the production startup configuration
- **THEN** the documented startup command points at the ASGI application entrypoint
- **AND** the runtime identifies the ASGI server used for deployment
