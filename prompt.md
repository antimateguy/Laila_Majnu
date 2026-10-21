# laila-majnu: Claude Code kickoff prompt (v1.0)

> Put this file and `docs/LLD.md` in the root of an empty repository, then give this file to Claude Code.
> To create `docs/LLD.md`, export the "laila-majnu Low-Level Design v1.0" doc as Markdown.

---

## 1. Your role and mission

You are the lead engineer for **laila-majnu**, a privacy-first conversational analytics web app for adults (18+).

**What it does:**
- A user uploads a WhatsApp or Instagram DM export of their chats with a crush.
- A C++ engine compiled to WebAssembly parses, sanitizes and scores the chat **inside the browser**. It renders a detailed, fun "Film Report" dashboard instantly.
- An optional, consented call sends a small anonymous JSON summary to a Python API. The API asks a free LLM for a cinematic "film narrative".
- The user gets a shareable retro Bollywood-style banner.
- The user can anonymously donate text-free metrics to a research pool.

This is a university project that will be defended in front of a panel. Build it **systematically**: contracts first, tests first, small reviewed phases. No vibe-coding, no speculative features, no dead code.

`docs/LLD.md` is the design source of truth.
- If this prompt and the LLD disagree on a contract, the LLD wins.
- If something is ambiguous or missing, **ask me before inventing it**.

---

## 2. Non-negotiable guardrails

1. **Raw chat text never leaves the browser.**
   - The only network egress with chat-derived data is the `AbridgedPayload` and the opt-in, text-free `DonationRecord`.
   - Add an end-to-end "canary" test. A fixture chat contains a unique canary string; the test intercepts every `fetch`.
   - The test fails if any request body contains the canary, a participant name, or a key outside the JSON Schema.
2. **Total spend ₹0.**
   - Use only the services in section 4.
   - No paid tiers and no service that needs a card on file.
   - No analytics, trackers, ad SDKs or third-party runtime CDNs (Turnstile is the one allowed third-party script). Self-host fonts.
3. **Deterministic core.**
   - Every metric, both headline scores, confidence ranges and the tier are pure functions with golden-file tests.
   - The LLM writes prose only. A server-side fact-check gate rejects any narrative containing a number or milestone that is not in the payload.
4. **18+ only, two-person chats only.** Group exports are rejected with a friendly message.
5. **Persona is presentation, not data.**
   - The user picks Laila or Majnu and is *always* treated as the one chasing.
   - Persona only sets Hinglish verb gender (user: `karti`/`karte`; crush: honorific plural, gender-neutral), the poster set and the copy voice.
   - It never changes parsing, metrics, scores or tier.
6. **Gender is never an input to any score.** It exists only as an optional, self-reported `pairing` field on donations.
7. **Archetypes and posters need my approval.**
   - All tier names, taglines and art live in `web/src/content/archetypes.json` with `status: "draft" | "approved"` and `approved_by`.
   - Never invent final names or art. Use the placeholders `TBD` / DRAFT.
   - The production build must fail in CI if any entry is not approved.
8. **Art and IP rules.**
   - Original illustrations only: no actor photos, film stills, studio posters or logos, no AI lookalikes of real people.
   - No song lyrics or famous dialogue lines.
   - Character names appear only as text references, with a "fan tribute, not affiliated with any film or studio" line.
9. **No secrets in the repo.** Commit `.env.example` files only.
10. **Engine rules:**
    - C++20, no `std::regex` (hand-written scanners, or CTRE if needed), no exceptions across the Wasm boundary.
    - `-Oz` release builds, under 1 MB gzipped `.wasm`.
    - ASan and UBSan on in native test builds.
11. **Never weaken or delete a test to make it pass.** If a test is wrong, explain why and fix it explicitly.
12. **New dependencies need my approval** unless they are listed in section 4.
13. **Do not fabricate export formats.**
    - Build parsers against fixtures.
    - Where real anonymized exports are missing, write a fixture generator and mark the gap with `TODO(fixture-real)`. Tell me.

---

## 3. Product summary

### Flow
1. **Pre-warm.** The landing page pings `GET /v1/health` in the background to warm the serverless API.
2. **Onboarding.** Retro intro with the Laila–Majnu chase poster → 18+ gate → persona picker (Laila / Majnu) → platform export guide → file drop.
3. **Unpack.** A Web Worker:
   - unzips the file (fflate);
   - keeps only `_chat.txt` or `message_N.json`;
   - builds a UTC-offset transition table with `Intl`;
   - calls the Wasm engine.
4. **Local report.** The user answers "Which one is you?" (names are shown locally only). The engine then computes:
   - 22 metrics;
   - the Majnu Meter, the Chemistry Score and confidence ranges;
   - the tier and milestones.

   The 14-scene Film Report renders instantly and works fully offline.
5. **Narrative (optional).** Payload preview → consent → Turnstile → `POST /v1/analyze`. The returned film narrative appears as scene 14.
6. **Share.** The banner is drawn on `<canvas>` at 1080×1920 and 1080×1080, then shared via the Web Share API or downloaded as PNG.
7. **Exit.**
   - Optional "Take one for the gang" donation: separate consent, an outcome tap, optional pairing.
   - A receipt token lets the user withdraw later.
   - "Delete everything" wipes memory and storage.

### Final v1 feature list
See Appendix A. Copy it into `docs/FEATURES.md` in Phase 1 and treat it as the scope boundary.

---

## 4. Stack (pinned)

| Area | Choice |
| --- | --- |
| Engine | C++20, CMake ≥ 3.24, Emscripten, Catch2 v3, libFuzzer, yyjson |
| Web | Vite, TypeScript (strict), React 18, Tailwind CSS, fflate, Comlink, hand-rolled SVG charts, Canvas 2D, Vitest, Playwright |
| API | Python 3.12, FastAPI, Pydantic v2, httpx (async), `upstash-redis` (HTTP), `psycopg` 3, `tiktoken` (confirm the encoding name used by gpt-oss), pytest, ruff, mypy |
| Contracts | JSON Schema 2020-12 in `schemas/` is the single source of truth. `datamodel-code-generator` produces the Pydantic models and `json-schema-to-typescript` the TS types. CI fails on codegen drift |
| CI | GitHub Actions, with Dependabot, CodeQL, secret scanning, `pip-audit`, `npm audit`, and actions pinned by SHA |
| Web hosting | Cloudflare Workers static assets (wrangler) |
| API hosting | Vercel Hobby, Python runtime |
| Database | Neon Free Postgres |
| Cache and rate limit | Upstash Redis Free |
| Bot check | Cloudflare Turnstile |
| Batch sealing | GitHub Actions scheduled workflow |
| LLM chain | Groq `openai/gpt-oss-120b` → `openai/gpt-oss-20b` → `qwen/qwen3.8-27b` → Cloudflare Workers AI `@cf/meta/llama-3.1-8b-instruct` (REST) → metrics-only. Model ids live in config |

All hosting services are on free tiers that need no card.

---

## 5. Repository layout

```
laila-majnu/
├─ docs/            LLD.md, FEATURES.md, DECISIONS.md (ADR log), PRIVACY.md, DEPLOY.md
├─ schemas/         abridged_payload, analysis_result, donation_record, narrative, local_report,
│                   metric_policy, archetypes  (*.schema.json)
├─ engine/
│  ├─ include/lm/   core/, parse/, metrics/, abridge/, wasm/
│  ├─ src/
│  ├─ assets/       lexicons/{en,hinglish}/*.json, names_gazetteer.json, metric_policy.json, tier_policy.json
│  ├─ tests/        Catch2 tests, property tests, golden files
│  ├─ fuzz/         libFuzzer targets per parser
│  └─ wasm/         C ABI: lm_open, lm_participants, lm_analyze, lm_abridge, lm_score, lm_close
├─ fixtures/        generator, synthetic + anonymized exports, PII test set, expected outputs
├─ web/
│  └─ src/          worker/, engine-bridge/, screens/, report/scenes/, share/, charts/,
│                   content/{archetypes.json, insights.en.json, insights.hinglish.json}, types/gen.ts
├─ api/             app/{main.py, routes/, inference/, validation/, factcheck/, store/},
│                   prompts/narrative_v1.md, vercel.json, requirements.txt
└─ .github/workflows/
```

---

## 6. Key contracts (summary; full detail in docs/LLD.md)

### Engine
**Parsing**
- `IChatParser` Strategy interface: `platform()`, `capabilities()`, `sniff(head) -> float`, `parse(bytes, ctx, sink) -> ParseCode`.
- `WhatsAppParserStrategy` takes an injected `AndroidDialect` or `IOSDialect`. It must handle:
  - date order (DMY/MDY) inference;
  - U+202F before AM/PM and U+200E marks;
  - multi-line messages and system lines;
  - no reactions in the export;
  - minute-level timestamps on Android.
- `InstagramDMParserStrategy` repairs Latin-1 mojibake, merges `message_N.json` parts and re-sorts newest-first data. It reads reactions.
- `ParserRegistry::detect` picks the highest sniff score ≥ 0.5.
- `ITimezoneResolver` is fed by the JS transition table.
- `ChatLogBuilder` owns an arena, sorts messages and rejects chats with more than 2 participants.

**Sanitizer**
- Participant names → `[SELF]`/`[OTHER]`.
- Phones (+91, 10-digit, spaced or dashed) → `[PHONE]`; emails → `[EMAIL]`; UPI IDs → `[UPI]`; URLs → `[LINK]`; @handles → `[HANDLE]`.
- Aadhaar-like and PAN-like numbers → `[ID]`; PIN codes and other 4+ digit numbers → `[NUM]`.
- Third-party first names (from a gazetteer) → `[NAME]`.
- Masking runs before any text is eligible as an excerpt.

**Metrics (22)** — exact definitions are in the LLD Metric catalogue.

| Family | Metrics |
| --- | --- |
| Pursuit | initiation share; effort share; double-text rate + timing (< 30 min / > 4 h); reply speed (P50/P90, latency gap); pursuer–distancer index |
| Responsiveness | turn-toward rate; follow-up question rate; dry-reply rate |
| Synchrony | LSM (9 function-word categories, English + Hinglish); length mirroring; emoji mirroring; rhythm overlap; longest rally |
| Warmth | affection rate + who said it first; we-talk; shared laughter; night-owl index |
| Friction | conflict-by-text; ghosts and comebacks; breadcrumbs |
| Momentum | momentum (Theil–Sen); fast-start fade |

**Scores**
- **Majnu Meter (0–100): how one-sided is the user's chase.** It is the mean of five 0–1 terms, where 0.5 means balanced:
  - SELF initiation share;
  - SELF message share;
  - SELF double-text share;
  - latency gap = other_p50 / (self_p50 + other_p50);
  - SELF share of pursuer–distancer episodes.

  Below 35 triggers the plot-twist reveal ("they chase you").
- **Chemistry Score (0–100):**
  - 0.25 × turn-toward rate (minimum of the two sides)
  - \+ 0.20 × LSM rescaled from 0.5–1 to 0–1
  - \+ 0.15 × reciprocity
  - \+ 0.15 × warmth
  - \+ 0.10 × rhythm overlap
  - \+ 0.15 × momentum (0 / 0.5 / 1)
  - − up to 15 friction points.

  All weights live in `metric_policy.json`.
- **Tier grid:** rows are Chemistry High (≥ 70), Mid (40–69) and Low (< 40). Columns are Majnu Meter > 65, 35–65 and < 35. This gives `Tier_01`–`Tier_09` in row-major order. `Tier_00` is trailer mode (< 300 messages or < 14 days).
- **Confidence:** each metric reports `n` and a level. Headline scores and latency medians get a 90% range from a seeded bootstrap over sessions (200 resamples). Fewer than 30 relevant events counts as low confidence.

**Milestones and payload**
- Change points: robust z-score with |z| > 2.5, plus discrete events.
- Salience: S = 0.40·min(|z|/4, 1) + 0.30·w_event + 0.15·r_vol + 0.15·r_shift.
- Selection: greedy MMR (λ = 0.7, τ = 14 days) under a 1,300-token knapsack, N ≤ 8, with the first and last sessions seeded.
- Excerpts: masked, ≤ 4 per milestone, ≤ 80 chars each.
- Token estimator must over-estimate: ceil(ASCII bytes / 4) + non-ASCII codepoints + 2 × emoji.

**C ABI**
- `lm_analyze` returns `LocalReport` JSON. It contains metrics, confidence, tier, weekly series, monthly initiation, a 6-bucket latency histogram, two 7×24 heatmaps, ghost list, top emojis, LSM categories, local milestones with excerpts, score inputs and the fingerprint seed. It never leaves the device.
- `lm_abridge` returns the `AbridgedPayload`.
- `lm_score(handle, score_inputs_json)` reruns only `ScorePolicy`, for the what-if sliders (< 16 ms).
- `lm_close` zeroes the arena before freeing.

### Dashboard: the Film Report (14 scenes)

| # | Scene |
| --- | --- |
| 1 | Poster |
| 2 | Box Office |
| 3 | The Chase |
| 4 | Reply Race |
| 5 | Who Starts the Scene |
| 6 | The Bids Ledger |
| 7 | Vibe Match |
| 8 | Night Shift |
| 9 | Warmth |
| 10 | Friction & Ghosts |
| 11 | The Storyboard |
| 12 | Director's Cut (what-if) |
| 13 | Texting Fingerprint |
| 14 | The Narrative (optional) |

**Every card has:**
- a fun title;
- a hero number;
- an SVG visual;
- a deterministic insight line from `insights.{en,hinglish}.json`;
- a confidence chip;
- a "How is this calculated?" sheet.

**Look and feel**
- Retro cinema: film grain, marquee bulbs, film-strip dividers, VHS title cards, tier palettes. Dark mode by default.
- Respect `prefers-reduced-motion`.
- Every chart has a text and table fallback, and WCAG AA contrast.

Visual details per scene are in the LLD Dashboard section.

### API

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/v1/health` | Pre-warm plus provider and circuit-breaker state |
| GET | `/v1/policy` | Tier thresholds and `metric_policy_version` |
| POST | `/v1/analyze` | `AbridgedPayload` → `AnalysisResult`. 16 KB cap; size checked before parsing; JSON depth ≤ 8; Turnstile; 10 req/min/IP; idempotent on `request_id` for 24 h; cache on SHA-256 of the canonical payload |
| POST | `/v1/donations` | `DonationRecord` → `{donation_id, receipt_token}`. 8 KB cap; receipt stored as SHA-256 |
| DELETE | `/v1/donations/{id}` | Header `X-Receipt-Token`; allowed until the batch is sealed |

**Validation**
- Pydantic models use `extra="forbid"`.
- Every `text` field is re-scanned for PII. Any hit → 422 `PII_DETECTED`, and nothing is forwarded.
- Tokens are recounted exactly. If the count exceeds 1,400, drop the lowest-salience milestones.

**Inference**
- Use one `InferencePort` interface, with one class per provider.
- Groq calls use `response_format: json_schema` with `strict: true`, `reasoning_effort: "low"`, `max_completion_tokens: 900` and `include_reasoning: false`.
- Qwen and Workers AI use JSON mode plus one repair attempt.
- Timeouts: 15 s per Groq call and 20 s for Workers AI, within a 25 s total budget.
- Each provider has a circuit breaker in Redis: it opens after 3 consecutive 429/5xx responses, for 60 s.
- A `429` moves straight to the next provider; it is not retried.

**Fact-check gate**
- Every number in the narrative must appear in the payload (allowing for rounding).
- Every milestone id must exist, and there are no unsent quotes.
- On failure, retry once, then move to the next provider.
- If everything fails: `status: "degraded"` with `narrative: null`, but `tier` is still returned (it comes from the server-side pure `TierPolicy`).

**Narrative prompt** — `api/prompts/narrative_v1.md`, static part first so it can be cached:
- Bollywood-trailer narrator voice.
- Hinglish when `hinglish_share` ≥ 0.4.
- Persona-correct verb gender for the user; honorific plural for the crush.
- Three acts tied to milestones.
- Cite payload numbers only; quote at most one excerpt.
- No diagnosis, no gender stereotypes, no manipulation advice.
- Set `boundary_signal` if the crush asked for space. When set: no jokes and no share card.

**Hygiene**
- Never log request bodies.
- CORS allows the web app's exact origin only.
- No cookies.

**Donations**
- The Neon table stores no IP and no user agent, and only the month.
- The Neon role can only `INSERT`, plus `DELETE` by id and token hash.
- A scheduled GitHub Actions workflow seals batches every `DONATION_BATCH_SIZE` records (default 50, max 100) and exports them as JSONL.

**Web security headers**
- CSP: `default-src 'self'`, `script-src 'self' 'wasm-unsafe-eval' https://challenges.cloudflare.com`.
- `connect-src` allows `'self'` and the API origin; `frame-src` allows Turnstile only.
- `object-src 'none'`, `base-uri 'none'`.
- Trusted Types on; no inline scripts; no `dangerouslySetInnerHTML` (enforced by a lint rule).
- HSTS, `Referrer-Policy: no-referrer`, and a minimal `Permissions-Policy`.

### Environment variables
- API (`api/.env.example`):
  - `GROQ_API_KEY`, `CF_ACCOUNT_ID`, `CF_AI_TOKEN` (Workers AI scope only)
  - `DATABASE_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`
  - `TURNSTILE_SECRET`, `ALLOWED_ORIGIN`
  - `LLM_CHAIN` (comma-separated `provider:model`), `DONATION_BATCH_SIZE=50`
- Web: `VITE_API_BASE`, `VITE_TURNSTILE_SITE_KEY`.

---

## 7. Quality bars (CI-enforced where possible)

### Accuracy
- Parsing is 100% correct on fixtures (messages, senders, UTC timestamps).
- Sanitizer recall is ≥ 99% on the labelled Indian PII set, with zero leaks of names or the canary.
- Each of the 22 metrics has hand-computed unit tests.
- Property tests check that:
  - swapping SELF and OTHER mirrors the paired metrics;
  - shifting all timestamps changes nothing;
  - reordering messages with equal timestamps changes nothing.
- Native and Wasm builds produce identical `LocalReport`s (floats within 1e-9).
- The narrative fact-check gate is tested.

### Robustness
- libFuzzer runs 5 minutes per parser on each push to `main`; longer runs nightly.
- Limits: 50 MB upload, 200K messages, 256 MB Wasm memory, 30 s worker timeout with Cancel.
- Metrics are fail-soft: one failing metric marks its card unavailable, and the rest of the report still renders.
- Error codes map to friendly English and Hinglish messages.

### Speed

| Budget | Target |
| --- | --- |
| First contentful paint (mid-range Android, 4G) | < 1.5 s |
| Initial JS | < 150 KB gzipped |
| Wasm | < 1 MB gzipped, loaded lazily with `instantiateStreaming` |
| Analyze 50K messages | < 2 s desktop, < 5 s low-end Android |
| First report scene | < 300 ms |
| What-if recompute | < 16 ms |
| `/v1/analyze` p95 | < 6 s (Groq structured outputs cannot stream, so a typewriter loading scene covers the wait) |
| `/v1/analyze` cache hit | < 300 ms |

### Privacy
- The canary end-to-end test passes.
- A log-scanner test confirms no request body reaches logs.

---

## 8. Phases and definitions of done

Work one phase at a time. At the end of each phase:
1. Run all checks.
2. **Stop** and post a summary:
   - what was built;
   - test counts and results;
   - bundle and Wasm sizes;
   - timing numbers;
   - deviations, recorded in `docs/DECISIONS.md`;
   - open questions.
3. Wait for my "go" before starting the next phase.

**Phase 1: Scaffold**
- Monorepo layout, `docs/FEATURES.md` from Appendix A, and `docs/DECISIONS.md`.
- JSON Schemas for every DTO and `LocalReport`, built from the LLD examples, plus codegen.
- CI workflows.
- `archetypes.json` with 20 `TBD`/draft entries, plus the production approval gate.
- A seeded fixture generator. It must produce:
  - WhatsApp Android and iOS exports, in 12 h and 24 h, DMY and MDY;
  - Instagram exports with mojibake and split files;
  - Hinglish messages and the canary string.
- The labelled PII test set.

*Done when:* CI is green on a wired skeleton, and fixtures regenerate byte-identically from the seed.

**Phase 2: Parsers**
- Core types, both strategies and their dialects, the registry, timezone resolvers, `ChatLogBuilder`, and the fuzzers.

*Done when:*
- every fixture parses to the expected counts, senders and UTC timestamps;
- groups are rejected;
- ambiguous date order is resolved or reported;
- mojibake round-trips correctly;
- fuzzers run clean.

**Phase 3: Metrics and scores**
- Lexicons, the sessionizer, all 22 metrics, confidence ranges, `ScorePolicy`, the tier policy, trailer mode, and `lm_score`.

*Done when:*
- unit, property and golden tests pass;
- the native-vs-Wasm determinism job is green.

**Phase 4: Abridgment and Wasm**
- Sanitizer, milestone detection, the MMR selector, the token estimator, the payload builder, the Emscripten build and the Comlink worker bridge.

*Done when:*
- the payload validates against its schema;
- no PII or canary survives;
- the token estimate is ≥ tiktoken's count on all fixtures;
- the Wasm is under 1 MB gzipped;
- the 50K-message timing is recorded.

**Phase 5: Web app, local-only**
- Onboarding: persona picker, 18+ gate, export guides, file drop, "which one is you?".
- All 14 Film Report scenes, with DRAFT archetypes.
- Share canvas and "delete everything".

*Done when:*
- Playwright runs the full flow on every fixture with the network disabled;
- the canary test passes;
- Lighthouse accessibility is ≥ 90;
- the speed budgets are met on desktop.

**Phase 6: Design review (my gate)**
- Build a review page that shows every archetype entry on its poster and banner templates, and every insight line in context.
- I will edit and approve entries in `archetypes.json`.
- Implement any art I supply.

*Done when:* I say so.

**Phase 7: API and inference**
- Routes, validation, the PII re-scan, token recount, Redis cache, rate limit and circuit breaker, Turnstile.
- The provider adapters, fallback chain, fact-check gate, degrade path and narrative prompt.
- Vercel config and pre-warm.
- Payload preview and consent screens in the web app.

*Done when:*
- every chain step and failure mode is covered by tests with mocked providers;
- a manual live smoke test with my keys returns a valid narrative;
- you have recorded whether Groq quotas are per model.

**Phase 8: Donations**
- Consent screen, outcome tap, optional pairing.
- `/v1/donations`, receipt-token delete, the Neon schema and migration, least-privilege role, and the batch-sealing workflow.

*Done when:*
- malformed records are rejected;
- delete works until a batch is sealed;
- sealed batches export as JSONL.

**Phase 9: Hardening and launch**
- Every quality bar is green.
- Low-end Android pass, accessibility pass, privacy review against `docs/PRIVACY.md`.
- A load test that stays within free limits.
- `docs/DEPLOY.md`.
- The production build gate passes (all archetypes approved).

---

## 9. Working agreements

- **Tests and commits.** Test-first for the engine and API. Use conventional commits, small and focused.
- **Engine code.** Keep functions small and pure, with no global state and no allocation in `sniff`.
- **Deviations.** Every deviation from the LLD gets a short ADR in `docs/DECISIONS.md`: context, decision, consequence.
- **Comments.** Explain the *why*, not the *what*.
- **Outdated facts.** If a free-tier limit, model id or API parameter here looks outdated against the provider docs, stop and tell me instead of silently changing it.

---

## 10. Start now

Begin **Phase 1 (Scaffold)**.
1. First, show me the file tree you intend to create and the JSON Schema for `AbridgedPayload`.
2. Then implement the phase.
3. Stop with the summary described in section 8.

---

## Appendix A: v1 feature list (final, 21 Oct 2026)

**Onboarding**
- F1 Retro cinematic intro with the Laila–Majnu chase poster, skippable
- F2 18+ gate (self-declared)
- F3 Persona picker: Laila or Majnu (the user is always the one chasing)
- F4 Step-by-step export guides: WhatsApp Android, WhatsApp iPhone, Instagram
- F5 File drop or picker: `.txt`, `.zip`, Instagram `.json`/`.zip`
- F6 "Which one is you?" picker, names shown only on the device
- F7 Privacy badge and on-device progress

**Film Report (instant, local, works offline)**
- F8 Poster scene: tier, archetype, film title, Majnu Meter, Chemistry Score
- F9 Box Office strip: messages, days, sessions, longest rally, 2 AM talks, top emojis
- F10 The Chase and Who Starts the Scene
- F11 Reply Race, yours vs theirs, with trend
- F12 The Bids Ledger: turn-toward rate, follow-up questions, Hmm-count
- F13 Vibe Match: LSM, emoji and length mirroring
- F14 Double-text stats with timing
- F15 Warmth: affection, who said ❤️ first, we-talk, shared laughter
- F16 Friction & Ghosts: silences, comebacks, breadcrumbs, conflict texting, pursuer–distancer
- F17 The Storyboard: weekly timeline with milestone frames
- F18 "How is this calculated?" sheet per metric, with the research source
- F19 Trailer mode for small chats
- F30 Director's Cut: what-if sliders with live scores
- F31 Texting Fingerprint generative art
- F32 Confidence chips and ranges on every card
- F33 Plot-twist reveal when they chase you more
- F34 Night Shift heatmaps

**AI narrative (optional, consented)**
- F20 Payload preview + consent + bot check
- F21 Film narrative: title, tagline, 3 acts, verdict, up to 3 tips; Hinglish or English, persona-correct grammar
- F22 "Narratives are busy" state; the report stays complete
- F23 Boundary-respect mode

**Share**
- F24 Share banner in 9:16 and 1:1 with swappable stats
- F25 Banner never shows the other person's name or words

**Exit and donation**
- F26 "Take one for the gang" donation with outcome tap and optional pairing
- F27 Donation receipt and withdraw option
- F28 "Delete everything" button

**Platform**
- F29 Mobile-first, tuned for low-end Android

**Out of scope for v1:**
- group chats;
- Telegram or Snapchat;
- accounts or login;
- server-side history;
- comparing multiple crushes;
- push notifications;
- paid features;
- Devanagari Hindi and other Indian languages;
- an installable app;
- percentile comparison with the donation pool.
