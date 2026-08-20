# Pilot Data Retention Policy

- Raw trend observations: 90 days by default; tenant-configurable from 30–730 days.
- Aggregated sales, scores, approvals, and audit events: retained for the pilot contract period plus 90 days.
- Agent prompts/traces: retain only redacted inputs and outputs for 30 days unless an incident hold applies.
- Raw customer PII is not required for recommendation workflows and must not be persisted in agent data.
- Secrets are stored by reference and never copied into exports, traces, or support tickets.
- Tenant deletion requests require a scoped export (if requested), deletion job, verification query, and audit receipt.

Retention deletion must run as a reviewed background job with dry-run counts before destructive execution.
