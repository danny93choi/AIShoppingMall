# Pilot Operations Playbook

1. Create the tenant and choose `conservative` or `growth` scoring preset.
2. Enable discovery and marketing drafts; keep external mutations disabled.
3. Connect a read-only Shopify test store and run the smoke check.
4. Run discovery, review Top 5 evidence, approve or reject, and record feedback.
5. Review workflow success, approval rate, cost per run, parse failures, and source failures weekly.
6. Escalate dead letters through the support endpoint; never retry permanent validation failures.
7. At pilot close, export agreed metrics, apply retention policy, and capture operator time saved.

Success metrics: recommendation view/approval rates, sample-sourcing conversion, listing conversion,
30-day recommended-product sales, operator time saved, workflow success, P95 duration, cost per run,
agent parse failure rate, and source failure rate.
