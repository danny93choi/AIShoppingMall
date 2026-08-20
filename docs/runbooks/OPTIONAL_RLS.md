# Optional PostgreSQL Row-Level Security

Application-layer tenant filtering remains mandatory. For production defense in depth, set a transaction-local `app.tenant_id` and enable a policy like:

```sql
ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;
CREATE POLICY recommendation_tenant_policy ON recommendations
USING (tenant_id = current_setting('app.tenant_id')::uuid)
WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
```

Roll out one table at a time after connection-pool and migration jobs set tenant context correctly. Fail closed when the setting is absent.
