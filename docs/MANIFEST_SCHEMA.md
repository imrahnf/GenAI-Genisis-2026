# DemoForge Preset Manifest Schema

Each preset may include a `manifest.json` in its sandbox directory (`sandboxes/<preset>/manifest.json`). The orchestrator and agent use it for context-driven behavior.

## Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Preset key (e.g. `preset`, `bank`). |
| `name` | string | yes | Display name. |
| `description` | string | yes | Short description for UI and agent. |
| `synthetic_data` | string | no | Note that data is synthetic/demo-only. |
| `endpoints` | array | no | List of `{ method, path, body?, description }`. |
| `example_commands` | array | no | Example curl commands; `{{base_url}}` is replaced with sandbox URL. |
| `default_goal` | string | no | Default agent goal. |
| `default_config` | object | no | Default env key/value for the container. |
| `config_schema` | object | no | Key → description for config fields (UI hints). |

## Example

See `sandboxes/preset/manifest.json` and `sandboxes/bank/manifest.json`.
