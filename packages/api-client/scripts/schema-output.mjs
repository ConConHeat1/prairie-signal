import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import openapiTS, { astToString } from "openapi-typescript";

export const packageRoot = resolve(import.meta.dirname, "..");
export const outputPath = resolve(packageRoot, "src/generated/schema.ts");
export const schemaPath = resolve(
  packageRoot,
  process.env.OPENAPI_SCHEMA_PATH ?? "../../apps/api/openapi.json",
);

export async function generateSchemaOutput() {
  // Reading explicitly gives a direct missing-artifact error before generation.
  const schema = JSON.parse(await readFile(schemaPath, "utf8"));
  const ast = await openapiTS(schema);
  return astToString(ast);
}
