# Profile schema — v1

`Profile` is the stable contract emitted by `aiprobe` and consumed by the
multi-provider gateway. This document is normative: any change here is a
schema-version bump.

**Current version:** `1`
**Frozen:** every model uses `extra="forbid"` and `frozen=True`.

## Top-level `Profile`

| Field             | Type                          | Required | Description                                                                   |
|-------------------|-------------------------------|----------|-------------------------------------------------------------------------------|
| `schema_version`  | `int`                         | no (1)   | Schema version. Defaults to `CURRENT_SCHEMA_VERSION`.                         |
| `target`          | `str`                         | yes      | Canonical target URL.                                                         |
| `detected_at`     | `datetime` (UTC)              | yes      | When the probe ran. Must be timezone-aware; normalized to UTC.                |
| `antibot`         | `AntibotInfo`                 | yes      | See below.                                                                    |
| `transport`       | `TransportInfo`               | yes      | See below.                                                                    |
| `auth`            | `AuthInfo`                    | yes      | See below.                                                                    |
| `endpoints`       | `dict[str, EndpointInfo]`     | yes      | Keyed by logical name (`"chat"`, `"models"`, …).                              |
| `stream_format`   | `StreamFormat`                | yes      | One of `none`, `sse`, `jsonl`, `chunked`, `unknown`.                          |
| `tool_calling`    | `bool`                        | yes      | Whether the target exposes OpenAI-style tool/function calling.                |
| `schema_compat`   | `SchemaCompat`                | yes      | One of `openai`, `custom`, `unknown`.                                         |
| `notes`           | `str \| null`                 | no       | Free-form notes.                                                              |

## `AntibotInfo`

| Field         | Type              | Required | Description                                                   |
|---------------|-------------------|----------|---------------------------------------------------------------|
| `type`        | `AntibotType`     | yes      | `none`, `cf-tls`, `cf-js`, `turnstile`, `datadome`, `unknown`.|
| `bypass`      | `BypassStrategy`  | yes      | `none`, `curl_cffi`, `browser`.                               |
| `impersonate` | `str \| null`     | no       | e.g. `"chrome"`. Only set when `bypass=curl_cffi`.            |
| `notes`       | `str \| null`     | no       |                                                               |

## `TransportInfo`

| Field             | Type           | Required | Description                                                 |
|-------------------|----------------|----------|-------------------------------------------------------------|
| `http2`           | `bool`         | yes      | Target requires/accepts HTTP/2.                             |
| `tls_fingerprint` | `str \| null`  | no       | e.g. `"chrome131"` if a specific fingerprint is required.   |
| `notes`           | `str \| null`  | no       |                                                             |

## `AuthInfo`

| Field      | Type              | Required | Description                                                          |
|------------|-------------------|----------|----------------------------------------------------------------------|
| `scheme`   | `AuthScheme`      | yes      | `none`, `cookie`, `bearer`, `header`, `unknown`.                     |
| `cookies`  | `list[str]`       | yes      | Names of cookies that carry the credential (e.g. `["token"]`).       |
| `refresh`  | `BypassStrategy`  | yes      | How to refresh credentials: `none`, `curl_cffi`, `browser`.          |

## `EndpointInfo`

| Field           | Type    | Required | Description                          |
|-----------------|---------|----------|--------------------------------------|
| `path`          | `str`   | yes      | Path portion, e.g. `/api/v1/chat`.   |
| `method`        | `str`   | yes      | HTTP verb, uppercase by convention.  |
| `requires_auth` | `bool`  | yes      | Endpoint rejects anonymous requests. |
| `validated`     | `bool`  | yes      | Endpoint was round-trip verified.    |

## Example

A fully valid v1 profile for a reference target:

```yaml
schema_version: 1
target: "https://chat.qwen.ai"
detected_at: "2026-01-01T12:00:00+00:00"
antibot:
  type: none
  bypass: none
  impersonate: null
  notes: null
transport:
  http2: true
  tls_fingerprint: null
  notes: null
auth:
  scheme: cookie
  cookies:
    - token
  refresh: none
endpoints:
  chat:
    path: "/api/v1/chat"
    method: "POST"
    requires_auth: true
    validated: true
stream_format: sse
tool_calling: true
schema_compat: openai
notes: "Reference example"
