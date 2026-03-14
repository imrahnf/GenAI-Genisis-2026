# DemoForge Preset Manifest Schema

Each preset may include a `manifest.json` in its sandbox directory (`sandboxes/<preset>/manifest.json`). The orchestrator and agent use it for context-driven behavior.

## Fields

| Field            | Type    | Required | Description |
|------------------|---------|----------|-------------|
| `id`             | string  | yes      | Preset key (e.g. `preset`, `bank`). |
| `name`           | string  | yes      | Display name. |
| `description`    | string  | yes      | Short description for UI and agent. |
| `synthetic_data` | string  | no       | Note that data is synthetic/demo-only. |
| `endpoints`      | array   | no       | List of `{ method, path, body?, description }`. Used to build the agent’s API context. |
| `example_commands` | array | no       | Example curl commands; `{{base_url}}` is replaced with sandbox URL. Also shown to the agent. |
| `default_goal`   | string  | no       | Default agent goal for this preset. |
| `default_config` | object  | no       | Default env key/value for the container (e.g. `APP_TITLE`, feature flags). |
| `config_schema`  | object  | no       | UI schema describing how to render config controls from `default_config`. |

### `config_schema` structure

`config_schema` maps each env var key to a **field descriptor** used by the frontend to render form controls. All fields are optional; sensible defaults are used when omitted.

```jsonc
"config_schema": {
  "APP_TITLE": {
    "label": "App title",                 // Optional label for the input
    "type": "text",                       // "text" | "number" | "boolean" | "select"
    "default": "Bank Demo",               // Optional default (usually matches default_config)
    "help": "Shown in the page title and header."
  },
  "BANK_CURRENCY": {
    "label": "Currency",
    "type": "select",
    "options": ["USD", "CAD", "EUR"],     // Required when type = "select"
    "default": "USD",
    "help": "Label for balances."
  },
  "SHOW_DEBUG": {
    "label": "Show debug banner",
    "type": "boolean",
    "default": false
  }
}
```

- The **frontend** reads this schema and renders the correct control for each key (text input, number input, checkbox, or select).
- The **backend** still only receives a plain `{ key: string }` `config` object in `/launch`; values are converted to strings before being passed as container env vars.

## Example manifests

See:

- `sandboxes/preset/manifest.json` — Favorite Foods preset (simple `APP_TITLE` text field).
- `sandboxes/bank/manifest.json` — Bank preset with `APP_TITLE` and `BANK_CURRENCY` (select) plus a `POST /api/seed` endpoint for efficient seeding.

## Manifest template

Use this as a starting point for new presets (save as `sandboxes/<preset-id>/manifest.json` and fill in the blanks):

```json
{
  "id": "my-preset",
  "name": "My Preset App",
  "description": "Short description of what this app does.",
  "synthetic_data": "Describe what synthetic data is used; no production data.",
  "endpoints": [
    {
      "method": "GET",
      "path": "/",
      "description": "Main HTML UI."
    },
    {
      "method": "POST",
      "path": "/api/example",
      "body": { "field": "string" },
      "description": "Example API call for the agent."
    }
  ],
  "example_commands": [
    "curl -s {{base_url}}/api/example -H 'Content-Type: application/json' -d '{\"field\":\"value\"}'"
  ],
  "default_goal": "Describe what the agent should do by default.",
  "default_config": {
    "APP_TITLE": "My Preset App"
  },
  "config_schema": {
    "APP_TITLE": {
      "label": "App title",
      "type": "text",
      "default": "My Preset App",
      "help": "Shown in the page title and header."
    }
  }
}
```

