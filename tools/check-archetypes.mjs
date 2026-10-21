// Archetype approval gate. Always checks shape and completeness; with
// --production it also requires every entry to be approved, which is what
// stops DRAFT names and art from shipping.
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { ROOT, createAjv, readJson, validatorFor } from "./lib/schemas.mjs";

export const ARCHETYPES_PATH = join(ROOT, "web", "src", "content", "archetypes.json");
const PLACEHOLDER = /\bTBD\b/i;

/** Returns a list of human-readable problems; empty means the file passes. */
export function checkArchetypes(doc, { production = false } = {}) {
  const validate = validatorFor(createAjv(), "archetypes.schema.json");
  if (!validate(doc)) {
    return validate.errors.map((e) => `schema: ${e.instancePath || "/"} ${e.message}`);
  }

  const problems = [];
  const seen = new Set();
  for (const e of doc.entries) {
    const key = `${e.tier_id}/${e.persona}`;
    if (seen.has(key)) problems.push(`${key}: duplicate entry`);
    seen.add(key);

    const expectedArt = `${e.tier_id.toLowerCase().replace("_", "")}_${e.persona.toLowerCase()}_`;
    if (!e.art_key.startsWith(expectedArt)) problems.push(`${key}: art_key ${e.art_key} does not belong to this tier/persona`);

    if (!production) continue;
    if (e.status !== "approved") problems.push(`${key}: not approved (status "${e.status}")`);
    const texts = [e.title, e.inspired_by, e.tagline.en, e.tagline.hinglish];
    if (texts.some((t) => PLACEHOLDER.test(t))) problems.push(`${key}: still contains a TBD placeholder`);
  }
  return problems;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const production = process.argv.includes("--production");
  const problems = checkArchetypes(readJson(ARCHETYPES_PATH), { production });
  if (problems.length) {
    console.error(`archetypes.json fails the ${production ? "production" : "development"} gate:`);
    for (const p of problems) console.error(`  - ${p}`);
    process.exit(1);
  }
  console.log(`archetypes.json passes the ${production ? "production" : "development"} gate.`);
}
