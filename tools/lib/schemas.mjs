import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
export const SCHEMA_DIR = join(ROOT, "schemas");

export function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

/** Every *.schema.json in schemas/, keyed by file name. */
export function loadSchemas() {
  return readdirSync(SCHEMA_DIR)
    .filter((f) => f.endsWith(".schema.json"))
    .sort()
    .map((file) => ({ file, schema: readJson(join(SCHEMA_DIR, file)) }));
}

/**
 * One strict Ajv instance holding every schema, so cross-file $refs resolve.
 * Strict mode turns schema typos (unknown keywords, untyped constraints) into
 * errors instead of silently accepting everything.
 */
export function createAjv() {
  const ajv = new Ajv2020({ strict: true, allErrors: true, strictRequired: false });
  addFormats(ajv);
  for (const { schema } of loadSchemas()) ajv.addSchema(schema);
  return ajv;
}

export function validatorFor(ajv, file) {
  const id = `https://laila-majnu.invalid/schemas/${file}`;
  const validate = ajv.getSchema(id);
  if (!validate) throw new Error(`schema not found: ${file}`);
  return validate;
}
