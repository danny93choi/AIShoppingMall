# PostgreSQL Backup and Restore Runbook

## Backup

1. Record the application version and Alembic revision.
2. Run `pg_dump --format=custom --no-owner --file=commerce.dump commerce` using an operator-only credential.
3. Encrypt the dump and store it outside the application host.
4. Record checksum, timestamp, tenant scope, and retention expiry.

## Restore drill

1. Create an isolated PostgreSQL instance; never overwrite production during a drill.
2. Verify the encrypted backup checksum and decrypt it in a temporary protected directory.
3. Run `pg_restore --clean --if-exists --no-owner --dbname=commerce_restore commerce.dump`.
4. Run `alembic current`, readiness checks, tenant-isolation tests, and recommendation-count checks.
5. Record recovery time, data timestamp, discrepancies, and delete the temporary decrypted dump.

Target cadence: monthly restore drill, daily encrypted backup, and documented recovery owner.
