import { describe, expect, it } from "vitest";
import { ARCHETYPES_PATH, checkArchetypes } from "../check-archetypes.mjs";
import { readJson } from "../lib/schemas.mjs";

const drafts = readJson(ARCHETYPES_PATH);
const approveAll = (doc) => {
  const copy = structuredClone(doc);
  copy.entries.forEach((e, i) => {
    Object.assign(e, {
      title: `Approved title ${i}`,
      inspired_by: `Character ${i}`,
      tagline: { en: `Tagline ${i}`, hinglish: `Tagline ${i}` },
      status: "approved",
      approved_by: "owner",
    });
  });
  return copy;
};

describe("archetype gate", () => {
  it("passes the committed drafts in development", () => {
    expect(checkArchetypes(drafts)).toEqual([]);
  });

  it("fails the committed drafts in production, once per entry", () => {
    const problems = checkArchetypes(drafts, { production: true });
    expect(problems.filter((p) => p.includes("not approved"))).toHaveLength(20);
  });

  it("passes production when every entry is approved", () => {
    expect(checkArchetypes(approveAll(drafts), { production: true })).toEqual([]);
  });

  it("fails production when one approved entry still says TBD", () => {
    const doc = approveAll(drafts);
    doc.entries[7].tagline.hinglish = "TBD";
    expect(checkArchetypes(doc, { production: true })).toEqual(["Tier_03/LAILA: still contains a TBD placeholder"]);
  });

  it("rejects approval without an approver", () => {
    const doc = approveAll(drafts);
    doc.entries[0].approved_by = null;
    expect(checkArchetypes(doc).join()).toMatch(/^schema:/);
  });

  it("rejects a duplicate tier/persona pair", () => {
    const doc = structuredClone(drafts);
    doc.entries[1] = { ...doc.entries[0] };
    expect(checkArchetypes(doc)).toContain("Tier_00/MAJNU: duplicate entry");
  });

  it("rejects art that belongs to another tier", () => {
    const doc = structuredClone(drafts);
    doc.entries[2].art_key = "tier09_majnu_v1";
    expect(checkArchetypes(doc)).toEqual(["Tier_01/MAJNU: art_key tier09_majnu_v1 does not belong to this tier/persona"]);
  });
});
