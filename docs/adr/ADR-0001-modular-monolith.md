# ADR-0001: Modular Monolith with Worker

- Status: Accepted
- Date: 2026-08-19

## Context

The MVP needs API, scheduled/background execution, strong domain boundaries, and low operational
complexity. Pilot capacity does not justify independently deployed domain services.

## Decision

Use one Python codebase with deployable API and worker entry points. Keep domain, application,
integration, and infrastructure boundaries explicit so modules can be extracted later.

## Alternatives

- Microservices: rejected for MVP due to deployment and consistency overhead.
- Single API process for all work: rejected because background workflows need an independent
  lifecycle and scaling boundary.

## Consequences

The API and worker share code and releases. Dependency rules and tests must prevent infrastructure
details from leaking into the domain.

