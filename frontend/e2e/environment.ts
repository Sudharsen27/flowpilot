import path from "node:path";

export const e2eApiUrl = "http://127.0.0.1:8010";
export const e2eAppUrl = "http://127.0.0.1:3010";
export const e2eDatabaseUrl =
  "postgresql+psycopg://app@127.0.0.1:5433/flowpilot_e2e";
export const e2ePostgresPort = "5433";
export const e2eWebhookSecret =
  "whsec_" + Buffer.from("0123456789abcdef01234567").toString("base64");

export const frontendDir = path.resolve(__dirname, "..");
export const backendDir = path.resolve(frontendDir, "../backend");
export const e2ePostgresDir = path.resolve(frontendDir, ".e2e-postgres");

export function e2ePostgresMode(): "private" | "external" {
  const mode = process.env.E2E_POSTGRES_MODE ?? "private";
  if (mode !== "private" && mode !== "external") {
    throw new Error("E2E_POSTGRES_MODE must be private or external");
  }
  return mode;
}

export function e2eProcessEnv(): Record<string, string> {
  return {
    PATH: process.env.PATH ?? "",
    HOME: process.env.HOME ?? "",
    LANG: process.env.LANG ?? "C.UTF-8",
    TMPDIR: process.env.TMPDIR ?? "/tmp",
    ENVIRONMENT: "test",
    DATABASE_URL: e2eDatabaseUrl,
    OPENAI_API_KEY: "",
    GROQ_API_KEY: "",
    RESEND_API_KEY: "",
    TYPESAFE_API_KEY: "",
    RESEND_WEBHOOK_SECRET: e2eWebhookSecret,
    RESEND_INBOUND_DOMAIN: "inbound.e2e.test",
    SECRET_KEY: "e2e-only-secret-key-not-for-production-use",
    AI_PROVIDER: "openai",
    API_HOST: "127.0.0.1",
    API_PORT: "8010",
    E2E_POSTGRES_DIR: e2ePostgresDir,
    E2E_POSTGRES_PORT: e2ePostgresPort,
    E2E_POSTGRES_MODE: e2ePostgresMode(),
    PYTHONPATH: backendDir,
  };
}
