# Decision log (ADRs)

Each entry records a deviation from, or a gap-fill in, `docs/LLD.md`: context, decision, consequence.

## ADR-0001: Rates in side stats are fractions (0–1)
- **Context:** The Metric catalogue defines `double_text_rate` and `followup_q_rate` "per 100 turns"; the validation table says rates are 0–1 and the example uses 0.18.
- **Decision:** Both are fractions per turn (0–1). The UI multiplies by 100 for display.
- **Consequence:** One unit across all `*_rate` fields except affection/conflict (per 100 msgs) and we-talk (per 1,000 words).

## ADR-0002: `double_text_slow_share` added to the shared metrics block
- **Context:** Metric #3 splits double texts into < 30 min and > 4 h. `SideStats` has both shares, but the payload example carries only the fast share, and `LocalReport.metrics` reuses the payload shape, so F14 / scene 5 would lose the > 4 h stat.
- **Decision:** Add `double_text_slow_share` (0–1, required) to `side_stats`. `emoji_density` stays out (no scene uses it). Approved by the owner on 21 Oct 2026.
- **Consequence:** The payload grows by two numbers (~4 tokens). DonationRecord gains it too. Superseded in part by ADR-0008: like every metric, it may be null.

## ADR-0003: `length_mirroring` ranges −1 to 1
- **Context:** It is a Spearman correlation, but the validation table does not list it.
- **Decision:** Bound it to [−1, 1].

## ADR-0004: `first_affection` is nullable
- **Context:** The C++ struct uses side `-1` for "no affection yet"; the JSON example only shows the present case.
- **Decision:** `first_affection` is `null` or `{side, week}`.

## ADR-0005: Milestone `type` strings are SCREAMING_SNAKE of `MilestoneType`
- **Decision:** `FIRST, LAST, PEAK_VOLUME, LONGEST_SILENCE, COMEBACK, GHOST, LATENCY_SHIFT, EFFORT_FLIP, MIRRORING_SHIFT, FIRST_AFFECTION, LONGEST_RALLY, PURSUER_DISTANCER_BURST`, matching the example's `LATENCY_SHIFT`.

## ADR-0006: Text lengths count Unicode codepoints
- **Context:** "80 chars" is ambiguous across JS (UTF-16), Python and C++ (bytes).
- **Decision:** Codepoints everywhere. JSON Schema `maxLength`, Ajv and Pydantic already count codepoints; the engine's excerpt truncation must too (tested: 80 emoji pass, 81 ASCII chars fail).

## ADR-0007: Shared definitions live in `schemas/common.schema.json`
- **Context:** Persona, side, tier id, momentum and bounded numbers are used by several DTOs.
- **Decision:** One extra schema file, `common.schema.json`, with no root document. `metrics_block` and `milestone` stay in `abridged_payload.schema.json`, since the LLD defines them as "same shape as AbridgedPayload".
- **Consequence:** 8 schema files instead of the 7 listed in the prompt layout.

## ADR-0008: `LocalReport` types and score definitions the LLD leaves open
Approved by the owner on 21 Oct 2026.

- **Context:** The LLD uses `MetricId`, `ScoreInputs` and `LocalMilestone` without defining them, names reciprocity, warmth and friction without formulas, sets only the low-confidence cut, and requires fail-soft metrics without saying how a failed metric is represented.
- **Decision — types:**
  - `MetricId`: the 22 catalogue metrics in order: `initiation_share, effort_share, double_text, reply_speed, pursuer_distancer, turn_toward, followup_questions, dry_reply, lsm, length_mirroring, emoji_mirroring, rhythm_overlap, longest_rally, affection, we_talk, shared_laughter, night_owl, conflict, ghosts, breadcrumbs, momentum, fast_start_fade`.
  - Confidence keys: the 22 ids plus `majnu_meter`, `chemistry_score`, `latency_p50_self`, `latency_p50_other`, the four figures with 90% ranges.
  - `ScoreInputs`: `trailer_mode`; the raw Majnu terms, including both latency medians so the reply-speed slider works; the Chemistry components in 0–1 before weighting, with warmth and friction already folded using the policy caps.
  - `LocalMilestone` is the payload milestone. `monthly_initiation` holds session counts. `lsm_categories` are the 9 categories of Ireland et al. 2011.
- **Decision — score definitions** (weights and caps live in `metric_policy.json`; caps are v1 guesses to recalibrate against donated outcomes):
  - **Shares with an empty denominator are 0.5** (balanced), e.g. neither side double-texts.
  - **Majnu Meter** = round(100 × mean of the available terms): SELF's share of initiated sessions, of messages, of double texts, of pursuer–distancer episodes, and the latency gap other_p50 / (self_p50 + other_p50).
  - **Reciprocity** = effort balance = 1 − |2 × SELF's character share − 1|, per chat and per week. Consequence: it overlaps the Majnu Meter, so a very one-sided chat loses up to 15 Chemistry points.
  - **Warmth** = mean of min(1, lower side's affection rate / 2 per 100 messages), min(1, lower side's we-talk / 5 per 1,000 words), and shared laughter. Using the lower side means warmth needs both people.
  - **Friction** = mean of min(1, chat conflict rate / 2 per 100 messages), min(1, ghosts per 10 weeks / 2), min(1, breadcrumbs / 3), min(1, pursuer–distancer episodes per 10 weeks / 5). Penalty = 15 × friction.
  - **Chemistry** = clamp(100 × Σ wᵢxᵢ / Σ wᵢ over available components − penalty, 0, 100), rounded half up, with the LLD weights (turn-toward uses the lower side, LSM is rescaled from 0.5–1 to 0–1, momentum maps FADING 0 / STEADY 0.5 / RISING 1).
  - **Confidence:** under 30 relevant events is low (LLD); 30–99 is medium; 100 or more is high.
- **Decision — fail-soft:** every metric field in the shared metrics block is nullable, and null means "not measured", never zero. `LocalReport.unavailable` lists `{metric, code}` with code `INSUFFICIENT_DATA`, `NOT_SUPPORTED_BY_PLATFORM` or `COMPUTE_ERROR`. Scores drop null terms and renormalise. A score is null when under 60% of its weight is available (`min_available_weight`). Either score null ⇒ `Tier_00` and a "not enough data" message.
- **Consequence:** The narrative prompt must say that null means "not measured". The fact-check gate must never accept a number for a null field. `first_affection: null` is ambiguous on its own; `unavailable` tells "nobody said it yet" apart from "could not measure".

## ADR-0018: Director's Cut slider: turn-toward replaces follow-up questions
- **Context:** The LLD's scene 12 sliders are reply speed, initiation share and follow-up questions. Follow-up questions feed neither headline score (ADR-0008), so that slider would never move a dial.
- **Decision:** The third slider is SELF's turn-toward rate ("turning toward their bids"), the largest Chemistry input. Reply speed and initiation move the Majnu Meter, and turn-toward moves Chemistry, so both axes of the tier grid respond. Follow-up questions stay a card metric and a narrative tip. Approved by the owner on 21 Oct 2026.
- **Consequence:** Chemistry uses the lower side's turn-toward, so raising SELF's rate only changes the score when SELF is the lower side. The slider's help text has to say so.

## ADR-0009: AnalysisResult `provider` is null when degraded
- **Decision:** `complete` ⇒ narrative + provider, `degraded_reason: null`; `degraded` ⇒ reason, `narrative: null`, `provider: null`. `provider.name` is `groq` | `workers_ai`.

## ADR-0010: Tier thresholds validate against `metric_policy.schema.json#/$defs/tier_policy`
- **Context:** The layout has both `metric_policy.json` and `tier_policy.json` but lists one schema.
- **Decision:** One schema file, with the tier policy as a `$defs` entry.

## ADR-0011: Toolchain and Phase 1 dev dependencies
- **Context:** The development machine has no C++20 compiler; Docker Desktop is available. The owner approved `ajv`, `ajv-formats`, `eslint`, `typescript-eslint` and `eslint-plugin-react`.
- **Decision:**
  - Engine builds run in Ubuntu 24.04 (clang 18), in CI and locally through Docker. Python code targets 3.12.
  - `eslint-plugin-react` is **not** used: it does not support ESLint 10 (ESLint 9 is end-of-life), and core `no-restricted-syntax` bans `dangerouslySetInnerHTML`, `innerHTML`/`outerHTML` and `insertAdjacentHTML` without it.
  - Counted as parts of listed tools: `@vitejs/plugin-react` (Vite + React), `@tailwindcss/vite` (Tailwind), `@types/react*` (TypeScript), and `black`/`isort` pulled in by `datamodel-code-generator`.
- **Consequence:** Starlette warns that its test client wants `httpx2` instead of `httpx`. Switching needs owner approval; until then the warning is expected.

## ADR-0012: `request_id` is a pattern, not `format: uuid`
- **Context:** With both, `datamodel-code-generator` emits a `UUID` field and Pydantic then cannot apply the pattern.
- **Decision:** Keep only the lowercase-UUID `pattern`. The id stays a string, which also keeps the canonical payload hash stable.

## ADR-0013: Codegen
- **Decision:** `npm run codegen` writes `web/src/types/gen.ts` (json-schema-to-typescript) and `api/app/models/*_schema.py` (datamodel-code-generator, Pydantic v2, `extra="forbid"`, `Literal` enums, collapsed root models). Named `$defs` carry a `title` so both languages get named types. CI fails on drift (`codegen:check`), verified identical on Windows and Linux.
- **Consequence:** json-schema-to-typescript cannot express `if/then` or `prefixItems`, so codegen strips if/then-only `allOf` blocks and rewrites `prefixItems` to a tuple for TypeScript only. Those rules are enforced by Ajv (client) and must be enforced by hand-written Pydantic validators in Phase 7 (trailer ⇒ no milestones, `excerpt_mode: none` ⇒ no excerpts, `week ≤ span.weeks`, status/narrative coupling).

## ADR-0014: Fixture corpus is synthetic until real exports arrive
- **Context:** No real anonymized exports are available yet.
- **Decision:** A seeded, stdlib-only generator (`fixtures/generator/gen.py`) writes 14 fixtures, their expected outputs and a 412-row PII set. The expected-output contract and each format assumption are listed in `fixtures/README.md` and marked `TODO(fixture-real)`. PII spans are UTF-8 byte offsets, because the engine scans bytes. Zips are `ZIP_STORED` with fixed timestamps, since deflate output differs between zlib builds.
- **Consequence:** Phase 2 parsers are only as right as these assumptions until checked against real files. Regeneration is byte-identical across Windows/Python 3.13 and Linux/Python 3.12 (verified).

## ADR-0015: The production archetype gate runs on release, not on every push
- **Context:** All 20 entries are drafts until design review (Phase 6), so a per-push production build would keep CI red for months.
- **Decision:** Every push runs the development gate (schema, 20 unique tier/persona pairs, matching `art_key`) and the gate's own tests. `release-gate.yml` (tags `v*` and manual runs) runs `build:prod`, which fails unless every entry is `approved`, has `approved_by`, and contains no `TBD`.

## ADR-0016: `engine_version` comes from the CMake project version
- **Decision:** `project(... VERSION 0.1.0)` generates `lm/core/version.hpp`; a test pins it to the payload's semver pattern.

## ADR-0017: `docs/PRIVACY.md` and `docs/DEPLOY.md` are written in their phases
- **Decision:** They are not stubbed in Phase 1; PRIVACY.md lands with the privacy review (Phase 9) and DEPLOY.md with launch (Phase 9). Secret scanning is a GitHub repository setting, to switch on when the repo is created.
