import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { SCHEMA_DIR, createAjv, readJson, validatorFor } from "../lib/schemas.mjs";

const ajv = createAjv();
const example = (name) => readJson(join(SCHEMA_DIR, "examples", `${name}.json`));
const mutate = (doc, fn) => {
  const copy = structuredClone(doc);
  fn(copy);
  return copy;
};

describe("LLD examples validate", () => {
  for (const [schema, ex] of [
    ["abridged_payload.schema.json", "abridged_payload"],
    ["analysis_result.schema.json", "analysis_result"],
    ["analysis_result.schema.json", "analysis_result.degraded"],
    ["narrative.schema.json", "narrative"],
    ["donation_record.schema.json", "donation_record"],
    ["local_report.schema.json", "local_report"],
    ["metric_policy.schema.json", "metric_policy"],
  ]) {
    it(`${ex} -> ${schema}`, () => {
      const validate = validatorFor(ajv, schema);
      expect(validate(example(ex)), JSON.stringify(validate.errors)).toBe(true);
    });
  }
});

describe("AbridgedPayload", () => {
  const validate = validatorFor(ajv, "abridged_payload.schema.json");
  const base = example("abridged_payload");
  const accepts = (doc) => expect(validate(doc), JSON.stringify(validate.errors)).toBe(true);
  const rejects = (doc) => expect(validate(doc)).toBe(false);

  it("accepts first_affection null", () => accepts(mutate(base, (d) => { d.metrics.pair.first_affection = null; })));
  it("accepts trailer mode without milestones", () => accepts(mutate(base, (d) => { d.span.trailer_mode = true; d.milestones = []; })));
  it("accepts excerpt_mode none without excerpts", () => accepts(mutate(base, (d) => { d.excerpt_mode = "none"; d.milestones[0].excerpts = []; })));
  it("accepts an 80-codepoint emoji excerpt", () => accepts(mutate(base, (d) => { d.milestones[0].excerpts[0].text = "😂".repeat(80); })));

  it("rejects an unknown top-level key", () => rejects(mutate(base, (d) => { d.names = ["Riya"]; })));
  it("rejects an unknown metric key", () => rejects(mutate(base, (d) => { d.metrics.self.raw = "hi"; })));
  it("rejects a missing double_text_slow_share", () => rejects(mutate(base, (d) => { delete d.metrics.other.double_text_slow_share; })));
  it("rejects schema_version 2.0", () => rejects(mutate(base, (d) => { d.schema_version = "2.0"; })));
  it("rejects a lowercase role", () => rejects(mutate(base, (d) => { d.role = "majnu"; })));
  it("rejects 9 milestones", () => rejects(mutate(base, (d) => { d.milestones = Array(9).fill(d.milestones[0]); })));
  it("rejects 5 excerpts", () => rejects(mutate(base, (d) => { d.milestones[0].excerpts = Array(5).fill(d.milestones[0].excerpts[0]); })));
  it("rejects an 81-codepoint excerpt", () => rejects(mutate(base, (d) => { d.milestones[0].excerpts[0].text = "x".repeat(81); })));
  it("rejects milestone id m9", () => rejects(mutate(base, (d) => { d.milestones[0].id = "m9"; })));
  it("rejects an unknown milestone type", () => rejects(mutate(base, (d) => { d.milestones[0].type = "BREAKUP"; })));
  it("rejects a fractional majnu_meter", () => rejects(mutate(base, (d) => { d.metrics.pair.majnu_meter = 71.5; })));
  it("rejects a share above 1", () => rejects(mutate(base, (d) => { d.metrics.self.msg_share = 1.2; })));
  it("rejects length_mirroring below -1", () => rejects(mutate(base, (d) => { d.metrics.pair.length_mirroring = -1.1; })));
  it("rejects milestones in trailer mode", () => rejects(mutate(base, (d) => { d.span.trailer_mode = true; })));
  it("rejects excerpts when excerpt_mode is none", () => rejects(mutate(base, (d) => { d.excerpt_mode = "none"; })));
  it("rejects est_tokens over the 1,300 budget", () => rejects(mutate(base, (d) => { d.est_tokens = 1301; })));
});

describe("fail-soft metrics (ADR-0008)", () => {
  const payload = validatorFor(ajv, "abridged_payload.schema.json");
  const report = validatorFor(ajv, "local_report.schema.json");
  const result = validatorFor(ajv, "analysis_result.schema.json");
  const ok = (validate, doc) => expect(validate(doc), JSON.stringify(validate.errors)).toBe(true);

  it("accepts a null metric as 'not measured'", () =>
    ok(payload, mutate(example("abridged_payload"), (d) => { d.metrics.other.latency_p50_s = null; d.metrics.pair.lsm = null; })));
  it("accepts null headline scores", () =>
    ok(payload, mutate(example("abridged_payload"), (d) => { d.metrics.pair.majnu_meter = null; d.metrics.pair.chemistry_score = null; })));
  it("still requires every metric key, even when null", () =>
    expect(payload(mutate(example("abridged_payload"), (d) => { delete d.metrics.pair.lsm; }))).toBe(false));
  it("accepts an unavailable entry with a known code", () =>
    ok(report, mutate(example("local_report"), (d) => { d.unavailable = [{ metric: "lsm", code: "INSUFFICIENT_DATA" }]; })));
  it("rejects an unknown unavailable code", () =>
    expect(report(mutate(example("local_report"), (d) => { d.unavailable = [{ metric: "lsm", code: "OOPS" }]; }))).toBe(false));
  it("rejects an unavailable entry for a non-metric", () =>
    expect(report(mutate(example("local_report"), (d) => { d.unavailable = [{ metric: "majnu_meter", code: "COMPUTE_ERROR" }]; }))).toBe(false));
  it("accepts null score inputs and a null-score Tier_00", () =>
    ok(report, mutate(example("local_report"), (d) => {
      d.score_inputs.chemistry.lsm = null;
      d.tier = { id: "Tier_00", majnu_meter: null, chemistry_score: null, plot_twist: false };
    })));
  it("accepts a server tier with null scores", () =>
    ok(result, mutate(example("analysis_result.degraded"), (d) => { d.tier.majnu_meter = null; d.tier.chemistry_score = null; d.tier.id = "Tier_00"; })));
});

describe("MetricPolicy", () => {
  const validate = validatorFor(ajv, "metric_policy.schema.json");
  it("requires the warmth and friction caps", () =>
    expect(validate(mutate(example("metric_policy"), (d) => { delete d.chemistry.friction; }))).toBe(false));
  it("rejects a zero cap", () =>
    expect(validate(mutate(example("metric_policy"), (d) => { d.chemistry.warmth.affection_cap_per_100_msgs = 0; }))).toBe(false));
});

describe("AnalysisResult status coupling", () => {
  const validate = validatorFor(ajv, "analysis_result.schema.json");
  it("rejects complete without a narrative", () =>
    expect(validate(mutate(example("analysis_result"), (d) => { d.narrative = null; }))).toBe(false));
  it("rejects degraded with a narrative", () =>
    expect(validate(mutate(example("analysis_result.degraded"), (d) => { d.narrative = example("narrative"); }))).toBe(false));
  it("rejects degraded without a reason", () =>
    expect(validate(mutate(example("analysis_result.degraded"), (d) => { d.degraded_reason = null; }))).toBe(false));
});

describe("DonationRecord", () => {
  const validate = validatorFor(ajv, "donation_record.schema.json");
  it("rejects excerpts_included true", () =>
    expect(validate(mutate(example("donation_record"), (d) => { d.consent.excerpts_included = true; }))).toBe(false));
  it("rejects a 7-column weekly row", () =>
    expect(validate(mutate(example("donation_record"), (d) => { d.weekly[0].push(1); }))).toBe(false));
  it("rejects a request_id", () =>
    expect(validate(mutate(example("donation_record"), (d) => { d.request_id = "9b2f4c1e-7a35-4e0b-9d61-2f3c8a7e5b10"; }))).toBe(false));
});
