export type LogEntry = { ts: number; type: string; message: string };

export type Sandbox = {
  sandbox_id: string;
  url: string;
  port: number;
  goal: string;
  preset?: string;
  template_id?: string | null;
  expires_at?: number | null;
  capture_active?: boolean;
  capture_steps_count?: number;
  logs?: LogEntry[];
};

export type ConfigFieldSchema = {
  label?: string;
  type?: "text" | "number" | "boolean" | "select";
  default?: string | number | boolean;
  options?: (string | number)[];
  help?: string;
};

export type Preset = {
  id: string;
  name: string;
  description: string;
  synthetic_data?: string;
  capabilities?: string[];
  default_goal?: string;
  default_config?: Record<string, string>;
  config_schema?: Record<string, ConfigFieldSchema>;
};

export type Template = {
  id: string;
  name: string;
  preset: string;
  steps_count: number;
};
