import { execFileSync } from "node:child_process";

import { e2ePostgresDir, e2ePostgresMode, e2eProcessEnv } from "./environment";

export default function globalTeardown(): void {
  if (e2ePostgresMode() !== "private") {
    return;
  }
  execFileSync(
    "pg_ctl",
    ["-D", e2ePostgresDir, "stop", "-m", "fast"],
    { env: e2eProcessEnv() as NodeJS.ProcessEnv, stdio: "inherit" },
  );
}
