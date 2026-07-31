import { writeFile } from "node:fs/promises";

import {
  generateSchemaOutput,
  outputPath,
  schemaPath,
} from "./schema-output.mjs";

const output = await generateSchemaOutput();
await writeFile(outputPath, output);
process.stdout.write(`Generated ${outputPath} from ${schemaPath}\n`);
