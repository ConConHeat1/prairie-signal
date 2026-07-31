import { readFile } from "node:fs/promises";

import {
  generateSchemaOutput,
  outputPath,
  schemaPath,
} from "./schema-output.mjs";

const [expected, checkedIn] = await Promise.all([
  generateSchemaOutput(),
  readFile(outputPath, "utf8"),
]);

if (expected !== checkedIn) {
  process.stderr.write(
    `Generated API types are out of date.\nRun "pnpm api:generate" after updating ${schemaPath}.\n`,
  );
  process.exitCode = 1;
} else {
  process.stdout.write(
    "Generated API types match the backend OpenAPI schema.\n",
  );
}
