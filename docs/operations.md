# Operations Guide

## Running in CI

You can run `aiprobe` in a scheduled pipeline to detect API drift.

```yaml
# .github/workflows/drift.yml
- name: Validate all profiles
  run: aiprobe validate --all --json > drift_report.json
```

## Interpreting Drift

Exit code `2` means drift was detected. The JSON output will list changes:
- `{"endpoint": "chat", "action": "removed"}`: The API removed the endpoint.
- `{"endpoint": "models", "action": "added", "method": "GET", "path": "/api/v2/models"}`: A new endpoint appeared.
- `{"field": "antibot.type", "old": "cf-tls", "new": "cf-js"}`: The provider upgraded their anti-bot protection.

## Handling Target Changes

When a target changes its API:
1. Run `aiprobe probe <target>` to generate a new profile.
2. Diff the old and new YAML files.
3. Update any downstream gateway configuration to match the new profile.

## Updating Fixtures

If a provider changes its API schema, the offline tests might fail. Update the JSON fixtures in `tests/fixtures/` by capturing real responses (e.g., using `curl` or browser devtools) and sanitizing any PII.
