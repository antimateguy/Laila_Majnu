# laila-majnu — Low-Level Design v1.0

Oct 21, 2026 · @Modu

## Summary and design principles

The architecture holds: parse and sanitize on-device in C++/Wasm, send only a small abridged payload, spend one LLM call per analysis, and run every service on a no-card free tier that wakes in about a second. Two facts reshaped it. Groq retired `llama-3.1-8b-instant` from its free tier on 16 Aug 2026 ([Groq deprecations](https://console.groq.com/docs/deprecations)), so `openai/gpt-oss-120b` is now primary with three fallbacks. And Python on Cloudflare's free Workers plan is capped at 10 ms CPU per request, so the API runs on Vercel (see Deployment).

**Decisions locked on 21 Oct 2026:**

- Masked micro-excerpts are on by default, for richer narratives.
- 18+ only.
- English and romanized Hinglish, in the sanitizer, lexicons, LSM and the narrative voice.
- The donation pool seals a batch every 50 records (configurable up to 100).
- Total spend ₹0: no card on file anywhere, no service that sleeps for more than about a second.
- The user picks a persona, Laila or Majnu, and is always treated as the one chasing.
- Archetype names (Badshah, Prem, Paro, Geet …) and poster art are settled in design review and ship only with your approval.
- The v1 feature list is final (Appendix).

Principles every component below follows:

1. **Raw text never leaves the device.** The only network egress is the `AbridgedPayload` DTO, schema-validated on both sides, and the user can inspect it before sending.
2. **Deterministic core, probabilistic garnish.** Every number and the cinematic tier come from pure, testable functions. The LLM only writes the narrative, and a fact-check gate rejects any number it invents.
3. **One inference call per analysis, with a hard token budget.** The client estimates conservatively; the server counts exactly and trims.
4. **Graceful degradation.** Groq `gpt-oss-120b` → `gpt-oss-20b` → `qwen/qwen3.8-27b` → Cloudflare Workers AI → metrics-only. The report and share banner never wait on an LLM.
5. **Versioned contracts.** Every DTO carries `schema_version`; one JSON Schema generates the Pydantic models and the TypeScript types.
6. **Persona is presentation, not data.** `Role::LAILA` / `Role::MAJNU` is the user's persona, and the user is always the one chasing. It sets Hinglish verb gender, the poster set and the copy voice; parsing, metrics, scores and tier are identical for both.
7. **Two-person chats only in v1.** Group exports are detected and rejected with a clear message.
8. **Gender-neutral scoring.** Research on male–female texting differences shapes copy and the donated-data research questions, never an individual's score (see Metric catalogue).
9. **Every bar is enforced.** Accuracy, robustness, security and speed targets are tests or CI gates, not intentions (see Quality bars).

## System flow and sequence map

Steps 1–3 run entirely on the device and produce a full metrics report with no network at all; the cloud only ever sees the abridged JSON from step 4 onward, and only after the user consents.

&#91;embedded content: upload-to-share-card sequence · 10 steps across the device boundary\]

1. **Load.** The user passes the 18+ gate, picks `MAJNU` or `LAILA`, and drops the export; the page has already pinged `/v1/health` to warm the API. A Web Worker unzips the file (fflate), keeps only `_chat.txt` or the `message_N.json` parts, builds the UTC-offset table from `Intl`, and hands the bytes to Wasm with `lm_open`.
2. **Parse, mask, score, abridge.** The `ParserRegistry` sniffs the format and runs the matching strategy. The UI asks "which one is you?" using names that never leave the device. `lm_analyze` computes the 22 metrics and both scores; `lm_abridge` builds the `AbridgedPayload`.
3. **Local report.** Scores, charts and the tier render immediately. Everything up to here works with no network.
4. **Consent, then send.** The user sees the exact payload in a readable preview, ticks consent, passes Turnstile, and the client POSTs to `/v1/analyze` with a client-generated `request_id`.
5. **Server gate.** Pydantic validation (`extra="forbid"`), PII re-scan, exact token recount, per-IP rate limit, then a cache lookup on the SHA-256 of the canonical payload.
6. **Inference.** The `InferencePort` adapter calls Groq `openai/gpt-oss-120b` with a strict `json_schema`, `reasoning_effort: "low"`, `max_completion_tokens: 900`. On `429` or an invalid reply it tries `gpt-oss-20b`, `qwen/qwen3.8-27b`, then Workers AI, then degrades.
7. **Narrative back.** The reply is validated against the `Narrative` model; unknown milestone ids are rejected.
8. **Result.** `TierPolicy` maps the two scores to `Tier_00…Tier_09` deterministically and the server returns `AnalysisResult` with `status: complete` or `degraded`.
9. **Share card.** The banner is drawn on a `<canvas>` in story and square sizes and shared through the Web Share API or saved as PNG.
10. **Donate (optional).** A separate consent, one outcome tap and an optional pairing field send a text-free `DonationRecord`; a scheduled job seals batches of 50.

The Python service holds no session state; its only persistent state is the donation table.

## Multi-platform ingestion: `IChatParser`

Each export format is a Strategy behind one interface; a registry sniffs the first 4 KB and picks the highest-confidence strategy. Every strategy normalizes into the same `MessageEvent` stream, and declares `ParserCapabilities` so the metric engine knows what it cannot measure (WhatsApp exports carry no reactions; Android WhatsApp has minute-level timestamps only).

### What each format actually gives us

| Aspect | WhatsApp Android `.txt` | WhatsApp iOS `.txt` | Instagram DM `.json` |
| --- | --- | --- | --- |
| Container | `.txt`, or `.zip` with `_chat.txt` | `.zip` with `_chat.txt` | Meta "Download your information" zip, JSON option; `messages/inbox/<thread>/message_1.json`, `message_2.json`, … |
| Header shape | `21/10/26, 12:02 am - Name: text` | `[21/10/26, 12:02:13 AM] Name: text` | `{sender_name, timestamp_ms, content, reactions[], …}` |
| Time precision | minutes | seconds | milliseconds |
| Time zone | device wall-clock, no offset | device wall-clock, no offset | epoch ms (UTC) |
| Date order | locale-dependent (DMY / MDY) | locale-dependent | n/a |
| Reactions | not exported | not exported | `reactions[{reaction, actor}]`, no reaction timestamp |
| Quirks | multi-line messages have no header; system lines have no `Name:`; `<Media omitted>`; localized system strings | U+200E marks before attachment lines; U+202F before AM/PM | newest-first order; text is UTF-8 stored as Latin-1 (mojibake) and must be re-decoded; one thread split over several files |

These shapes come from public parsers and guides ([chatpack](https://docs.rs/crate/chatpack/0.6.0/source/docs/EXPORT_GUIDE.md), [igmd](https://github.com/kr3t3n/igmd), [WhatsR](https://cran.r-universe.dev/WhatsR/doc/manual.html)). Locale variants drift between app versions, so the first engineering task is a fixture corpus of \~30 real exports (anonymized) across Android/iOS, 12h/24h, English/Hindi phone language.

### Core types

```cpp
// lm/core/types.hpp
namespace lm {

enum class Platform : uint8_t { Unknown, WhatsApp, InstagramDM };
enum class Role     : uint8_t { MAJNU, LAILA };     // persona only (the user is always the chaser); never changes parsing or scores

using ParticipantId = uint8_t;                     // order of first appearance
inline constexpr ParticipantId kSystem = 0xFF;

enum class MessageKind : uint8_t { Text, Media, Sticker, Link, Deleted, System, CallLog };

struct Reaction {
  ParticipantId          actor;
  char32_t               emoji_base;   // first codepoint, skin-tone modifiers stripped
  std::optional<int64_t> ts_utc_ms;    // Instagram does not export reaction time
};

struct MessageEvent {
  uint32_t         seq;                // index after chronological sort
  int64_t          ts_utc_ms;
  int16_t          utc_offset_min;     // offset applied when converting wall-clock
  ParticipantId    sender;
  MessageKind      kind;
  std::string_view text;               // view into ChatLog's arena; raw, NOT yet sanitized
  uint32_t         codepoints;
  uint16_t         emoji_count;
  bool             edited;
  std::span<const Reaction> reactions; // into ChatLog's arena; empty when unsupported
};

struct ParserCapabilities {
  bool reactions;          // IG: yes   WA: no
  bool seconds_precision;  // WA iOS, IG: yes   WA Android: no
  bool edit_markers;
  bool explicit_timezone;  // IG: yes (epoch)   WA: no (wall-clock)
};

}  // namespace lm
```

### Time zones

Wasm has no tz database, and WhatsApp timestamps are wall-clock. JavaScript builds a table of UTC-offset transitions for the export's date span using `Intl` and the user's IANA zone, and hands it to C++. India has no DST, but users abroad do, so a single fixed offset is not enough.

```cpp
class ITimezoneResolver {
 public:
  virtual ~ITimezoneResolver() = default;
  // local wall-clock minutes (as if UTC) -> offset minutes east of UTC
  virtual int16_t offset_for_local(int64_t local_wall_min) const noexcept = 0;
};
class FixedOffsetResolver;      // e.g. +330 for Asia/Kolkata
class TransitionTableResolver;  // built from JS-supplied [{from_local_min, offset_min}]

enum class DateOrder : uint8_t { Auto, DMY, MDY, YMD };

struct ParseContext {
  const ITimezoneResolver* tz;        // required for wall-clock formats
  DateOrder date_order   = DateOrder::Auto;
  uint32_t  max_messages = 200'000;   // hard cap protects the browser tab
};
```

### The Strategy interface

```cpp
enum class ParseCode : uint16_t {
  Ok, EmptyInput, UnknownFormat, GroupChatRejected, AmbiguousDateOrder,
  NonMonotonicTime, MojibakeRepaired, MessageCapHit, MalformedRecord
};

class IMessageSink {             // implemented by ChatLogBuilder
 public:
  virtual ~IMessageSink() = default;
  virtual ParticipantId on_participant(std::string_view display_name) = 0;
  virtual void on_message(int64_t ts_utc_ms, int16_t offset_min, ParticipantId sender,
                          MessageKind kind, std::string_view text, bool edited,
                          std::span<const Reaction> reactions) = 0;
  virtual void on_warning(ParseCode code, uint32_t byte_offset) = 0;
};

class IChatParser {
 public:
  virtual ~IChatParser() = default;
  virtual Platform           platform()     const noexcept = 0;
  virtual ParserCapabilities capabilities() const noexcept = 0;
  // Inspect at most the first 4 KB. Pure, cheap, no allocation. Returns 0.0-1.0.
  virtual float     sniff(std::string_view head) const noexcept = 0;
  // One call per file; multi-file exports (IG message_N.json) call it once per part.
  virtual ParseCode parse(std::string_view bytes, const ParseContext& ctx, IMessageSink& sink) = 0;
};
```

### Concrete strategies

```cpp
// WhatsApp: one strategy, two injected dialects (Template Method inside, Strategy outside)
struct WhatsAppHeader { int64_t local_wall_min; int8_t seconds; std::string_view sender, body; };

class IWhatsAppDialect {
 public:
  virtual ~IWhatsAppDialect() = default;
  virtual std::optional<WhatsAppHeader> match_header(std::string_view line, DateOrder) const noexcept = 0;
  virtual MessageKind classify_body(std::string_view body) const noexcept = 0; // media/deleted/edited strings
  virtual bool        seconds_precision() const noexcept = 0;
};
class AndroidDialect final : public IWhatsAppDialect { /* "d/m/yy, h:mm am - " */ };
class IOSDialect     final : public IWhatsAppDialect { /* "[d/m/yy, h:mm:ss AM] " */ };

class WhatsAppParserStrategy final : public IChatParser {
 public:
  explicit WhatsAppParserStrategy(std::unique_ptr<IWhatsAppDialect> d);
  ParseCode parse(std::string_view, const ParseContext&, IMessageSink&) override;
 private:
  DateOrder infer_date_order(std::string_view bytes) const;  // any first field > 12 => DMY; check monotonicity
  std::unique_ptr<IWhatsAppDialect> dialect_;
};

class InstagramDMParserStrategy final : public IChatParser {
 public:
  ParseCode parse(std::string_view, const ParseContext&, IMessageSink&) override;
 private:
  static std::string repair_mojibake(std::string_view latin1_escaped); // Latin-1 code units -> UTF-8 bytes
};

class ParserRegistry {
 public:
  void add(std::unique_ptr<IChatParser> p);
  // Highest sniff wins; below 0.5 the UI asks the user to pick the platform.
  const IChatParser* detect(std::string_view head) const noexcept;
};
```

Implementation rules:

- **No `std::regex` in Wasm.** It is slow and bloats the binary. Use a hand-written line scanner, or compile-time regex (CTRE) if patterns get complex.
- **Unzip in JavaScript** (a small library such as fflate) inside the Web Worker; C++ receives only `_chat.txt` or the `message_N.json` parts. C++ stays format-pure and testable natively.
- **`ChatLogBuilder`** (the sink) owns one arena for text and reactions, sorts by `ts_utc_ms` on `finalize()`, assigns `seq`, and rejects threads with more than two non-system participants.
- **Participant names never leave C++ except to the local UI** for the "which one is you?" step. After that they are replaced by `SELF` / `OTHER`.

## Metric catalogue: what we measure and why

Twenty-two on-device metrics in six families feed two headline scores, the **Majnu Meter** (who chases) and the **Chemistry Score** (how connected), and those two scores place every chat on a 3 × 3 tier grid. Each metric has a published formula and is grounded either in relationship research or in a plain behavioural count.

### What the research says

| Finding | Source | How we use it |
| --- | --- | --- |
| Higher language style matching (LSM) in 40 speed dates predicted mutual interest (odds ratio 3.05); in 86 couples' instant messages, 76.7% of above-median-LSM couples were still dating at 3 months vs 53.5% below | [Ireland et al., Psychological Science 2011](https://pubmed.ncbi.nlm.nih.gov/21149854/) | **Vibe Match** (LSM), with English + Hinglish function-word lists |
| People who ask more questions, especially follow-ups, are better liked; speed daters who asked more follow-ups got more second-date agreements | [Huang et al., JPSP 2017](https://dash.harvard.edu/handle/1/42704282) | **Follow-up question rate** |
| Newlyweds still married after six years had turned toward each other's bids for connection 86% of the time; couples who divorced, 33% | [Gottman Institute](https://www.gottman.com/blog/turn-toward-instead-of-away/) | **Turn-toward rate**, a text adaptation (not comparable to lab percentages) |
| A meta-analysis of 30 studies (5,000+ people) links "we-talk" to satisfaction and longer relationships | [Karan, Rosenthal & Robbins 2018](https://news.ucr.edu/articles/2018/10/04/research-affirms-power-we) | **We-talk rate** |
| In 276 young adults: affectionate texts linked to satisfaction for both sexes, sending more than receiving; men's high texting frequency linked to lower satisfaction; women using texts to apologize or settle differences linked to lower quality. Exploratory, correlational | [Schade et al. 2013](https://scholarsarchive.byu.edu/facpub/2343), [BYU summary](https://news.byu.edu/news/too-much-texting-can-disconnect-couples-research-finds) | **Affection rate**, **Conflict-by-text rate**; no gender weighting |
| Demand/withdraw (one pushes, the other avoids) is stronger in unhappy couples (meta-analytic r = .36) | [Schrodt et al. meta-analysis, cited in a UCLA couples study](https://escholarship.org/content/qt9f58m8b5/qt9f58m8b5.pdf) | **Pursuer–distancer index** |
| Women included emojis in more messages than men (7.96% vs 7.02%) in a large Android dataset | [Chen et al. 2018](https://arxiv.org/pdf/1705.05546) | Emoji metrics compare each person to their own baseline; low emoji use is never penalized |
| In a two-week diary study, men's reported reply latency was longer than women's | [Bean 2015](https://digitalcommons.usu.edu/etd/4607) | Latency is judged against each person's own median, never across genders |
| Hinge app data: after a single text, reply odds drop from 55% to 38% within 30 minutes; a double text around the 4-hour mark beats waiting | [Reader's Digest on Hinge data](https://www.rd.com/article/wait-response-text-message/) (industry data, not peer-reviewed) | **Double-text timing** fun stat, labelled as app data |
| Online daters message people about 25% more desirable than themselves; 21% of these aspirational messages get replies | [Bruch & Newman, Science Advances 2018](https://m.medicalxpress.com/news/2018-08-game-online-dating-men-women.html) | Copy for "aspirational chase" tiers only |

**Male–female dynamics, and how we handle them.** The studies above report group averages that overlap heavily between individuals. Scoring someone by their gender would be both inaccurate and the first thing a panel attacks. So every metric compares a person to their own baseline and to their role, and gender is never an input to any score. Gender enters only as an optional, self-reported `pairing` field on donations (`M_F`, `F_M`, `SAME`, `UNDISCLOSED`), which lets the pool test these Western findings on Indian Hinglish chats: a genuine research contribution.

### The 22 metrics

| # | Family | Metric (UI name) | Definition |
| --- | --- | --- | --- |
| 1 | Pursuit | Initiation share ("Who texts first") | Share of sessions each side started |
| 2 | Pursuit | Effort share | Each side's share of messages and of characters |
| 3 | Pursuit | Double-text rate + timing | Messages sent with no reply since one's own last message, per 100 turns; split into < 30 min and > 4 h |
| 4 | Pursuit | Reply speed | Median and P90 latency per side; latency gap = other\_p50 / (self\_p50 + other\_p50) |
| 5 | Pursuit | Pursuer–distancer index | Episodes where one side sends ≥ 3 consecutive messages including a question within 2 h, and the other replies after > 3 × their own median latency or with ≤ 5 characters; counted per direction |
| 6 | Responsiveness | Turn-toward rate | Bids = questions, shared links/media, messages ≥ that person's P75 length, affection tokens. Turned toward = the other replies in the same session with a non-filler message |
| 7 | Responsiveness | Follow-up question rate | Questions in a reply turn that share a content word with the previous turn, per 100 turns |
| 8 | Responsiveness | Dry-reply rate ("Hmm-count") | Replies of ≤ 3 characters or filler only (`k`, `ok`, `hmm`, `haan`, `acha`, `lol`) |
| 9 | Synchrony | Vibe Match (LSM) | Mean over 9 function-word categories of 1 − abs(p\_A − p\_B) / (p\_A + p\_B + 0.0001) |
| 10 | Synchrony | Length mirroring | Spearman correlation of consecutive turn lengths |
| 11 | Synchrony | Emoji mirroring | Weekly Jaccard similarity of the two emoji sets |
| 12 | Synchrony | Rhythm overlap | Cosine similarity of the two 24-hour activity histograms |
| 13 | Synchrony | Longest rally | Most consecutive turn exchanges with every reply < 2 min |
| 14 | Warmth | Affection rate + "who said it first" | Affection tokens per 100 messages per side (`miss you`, `love`, ❤️, 😘, `jaan`, …); side and week of the first one |
| 15 | Warmth | We-talk rate | `we`, `us`, `our`, `hum dono`, `hum log`, `hamara` … per 1,000 words |
| 16 | Warmth | Shared laughter | Share of one side's laughter (`haha`, `lol`, 😂, 🤣 …) answered by laughter in the next turn |
| 17 | Warmth | Night-owl index ("2 AM talks") | Share of messages 23:00–04:00 local, and who sends the last message of late sessions |
| 18 | Friction | Conflict-by-text rate | Apology and conflict tokens (`sorry`, `maaf`, `why didn't you`, `whatever`, `fine.`) per 100 messages per side |
| 19 | Friction | Ghosts and comebacks | Silences > max(24 h, 10 × that side's median latency) after the other spoke last, and who broke each |
| 20 | Friction | Breadcrumb count | A comeback after a ghost that is ≤ 20 characters and is followed by another ghost within 7 days |
| 21 | Momentum | Momentum | Theil–Sen slopes of weekly volume and latency → `RISING`, `STEADY`, `FADING` |
| 22 | Momentum | Fast-start fade | (affection + volume in the last 4 weeks) / (same in the first 4 weeks) |

Lexicons (fillers, affection, laughter, apology/conflict, we-talk, the 9 LSM categories) are versioned JSON assets covering English and romanized Hinglish with spelling variants (`nahi`/`nhi`/`nai`). `hum` alone is ambiguous in Hinglish, so we-talk counts it only in fixed phrases. Messages are also tagged Hinglish or English per message, giving `hinglish_share`, which sets the narrative's language.

### Headline scores

**Majnu Meter (0–100, from `SELF`'s side).** The mean of five terms, each scaled 0–1 with 0.5 meaning balanced: SELF's initiation share, message share, double-text share, the latency gap (#4), and SELF's share of pursuer–distancer episodes. 50 is balanced; above 65 you chase; below 35 they chase.

**Chemistry Score (0–100).** 0.25 × turn-toward (the lower of the two sides) + 0.20 × LSM rescaled from 0.5–1.0 to 0–1 + 0.15 × reciprocity + 0.15 × warmth (affection, we-talk and shared-laughter reciprocity) + 0.10 × rhythm overlap + 0.15 × momentum (`FADING` 0, `STEADY` 0.5, `RISING` 1), minus up to 15 points for friction. These weights are v1 guesses kept in the versioned `metric_policy` file, to be recalibrated against `self_reported_outcome` once donations arrive.

### Tier grid

| Chemistry ↓ / How one-sided is the chase → | All you (Majnu Meter > 65) | Mutual (35–65) | Plot twist: they chase you (< 35) |
| --- | --- | --- | --- |
| High (≥ 70) | Tier\_01 | Tier\_02 | Tier\_03 |
| Mid (40–69) | Tier\_04 | Tier\_05 | Tier\_06 |
| Low (< 40) | Tier\_07 | Tier\_08 | Tier\_09 |

Chats with fewer than 300 messages or 14 days get `Tier_00` ("Trailer": a reduced report and no milestones). A `boundary_signal` suppresses the share banner entirely. Each tier has one archetype per persona; names and art come from the approved archetype file described next.

## Personas, tiers and posters

The user always plays the one who is chasing; choosing **Laila** or **Majnu** only picks their persona, which sets Hinglish verb gender, the poster character set and the copy voice, never a score.

**Persona.** `LAILA` uses feminine forms for the user ("tum reply karti rahi"), `MAJNU` masculine ("tum reply karte rahe"). The crush is always written with honorific plural forms ("unhone", "woh aaye"), which reads as gender-neutral, so the app never assumes the crush's gender. The persona is sent in the payload only so the narrative gets the grammar right.

**What the Majnu Meter means now.** Because the user is the chaser by definition, the meter answers "how one-sided is your chase?": above 65 it is all you, 35–65 it is mutual, and below 35 the report opens with a **plot-twist reveal**: they have been chasing you.

### Archetype file and approval gate

Tier names, film references, taglines and art live in one content file, `web/src/content/archetypes.json`, never in code: 10 tiers (`Tier_00`–`Tier_09`) × 2 personas = 20 entries.

```json
{
  "version": "2026-10-21",
  "entries": [
    {
      "tier_id": "Tier_04",
      "persona": "MAJNU",
      "title": "TBD in design review",
      "inspired_by": "TBD",
      "tagline": { "en": "TBD", "hinglish": "TBD" },
      "palette": ["#1B1035", "#F2C14E", "#E4572E"],
      "art_key": "tier04_majnu_v1",
      "status": "draft",
      "approved_by": null
    }
  ]
}
```

- **Starter pool from you, not yet assigned to tiers:** Badshah, Prem, Bhaskar, Ricky Bahl, Paro, Geet, and more from Bollywood and Hollywood as design explores.
- **Gate:** development builds show drafts with a "DRAFT" watermark; the production build fails in CI if any entry is not `"status": "approved"` with `approved_by` set. Approval is yours, entry by entry, and entries can be re-edited and re-approved later without code changes.
- The same file drives the onboarding "Laila–Majnu chase" poster, the report poster and the share banner.

### Poster and art rules

Indian courts are actively protecting actors' identities: the Delhi High Court has granted personality-rights orders to many Bollywood actors, and its order for Vivek Oberoi bars use of his name, voice, image or likeness without consent, including through AI, deepfakes and face morphing ([Bar & Bench](https://www.barandbench.com/news/delhi-high-court-protects-personality-rights-of-actor-vivek-oberoi), [Storyboard18](https://storyboard18.com/photos/trending/kajol-aishwarya-rai-jubin-nautiyal-and-more-list-of-celebrities-who-got-personality-rights-90991.htm)). So:

- Original illustrations only: no actor photos, film stills, studio posters or logos, and no AI-generated lookalikes of any real person.
- Character names appear only as playful text references to archetypes, never alongside an actor's name or face; every poster carries a small "fan tribute, not affiliated with any film or studio" line.
- No song lyrics or famous dialogue lines on posters or cards.
- Ask the university legal office to review the final archetype names before launch.

Posters render deterministically on `<canvas>` from layered templates: tier palette background, the archetype illustration (`art_key`, SVG), the film-title lockup in a self-hosted OFL-licensed retro display font, and the stats strip.

## Dashboard: the Film Report

The report is a scrolling "film" of 14 scenes built entirely from local data, so it renders in under 300 ms with no network and no LLM; the AI narrative, when consented, is one extra scene on top.

### Card anatomy

Every scene is a card with the same six parts, so the dashboard reads consistently and every number is explainable:

1. **Fun title** in the persona's voice ("Reply Race", "The Bids Ledger").
2. **Hero number** (the one figure to remember).
3. **Visual**, hand-rolled SVG, no chart library.
4. **Insight line**: a deterministic sentence chosen from `content/insights.{en,hinglish}.json` by metric and threshold band, so the report is witty even without the LLM.
5. **Confidence chip**: sample size plus low / medium / high. Headline scores and latency medians also get a 90% range from a seeded bootstrap over sessions (200 resamples). Cards with fewer than 30 relevant events are dimmed and say so.
6. **"How is this calculated?" sheet**: the formula in plain words and the research source from the Metric catalogue.

### Scenes

| # | Scene | What it shows | Visual | Fun hook |
| --- | --- | --- | --- | --- |
| 1 | Poster | Tier, archetype, film title, Majnu Meter, Chemistry Score | Poster art + two dials | Curtain-up reveal; "PLOT TWIST" stamp when the meter is below 35 |
| 2 | Box Office | Messages, days, sessions, longest rally, 2 AM talks, top 5 emojis each side | Ticker strip | Numbers roll up like a box-office board |
| 3 | The Chase | The five terms behind the Majnu Meter | Tug-of-war bar per term | "Who's pulling the rope?" |
| 4 | Reply Race | Both sides' reply-time distributions, medians, P90, weekly trend | Mirrored histograms in 6 buckets (< 1 m, 1–5 m, 5–30 m, 30 m–2 h, 2–8 h, > 8 h) + trend line | Race commentary copy |
| 5 | Who Starts the Scene | Initiation share by month; double-text timing | Stacked monthly bars | "Opening-line champion" |
| 6 | The Bids Ledger | Turn-toward rate both sides, follow-up questions, Hmm-count | Paired rings + counter | "Hmm-o-meter" |
| 7 | Vibe Match | LSM with its 9 categories, length and emoji mirroring | Paired bars; emoji pairs that both use | "Same wavelength?" |
| 8 | Night Shift | When each side texts, and the overlap | Two 7 × 24 heatmaps (day × hour) + overlap map | "2 AM philosophers" |
| 9 | Warmth | Affection over time, first ❤️ marker, we-talk, shared laughter | Line with a marked first-affection frame | "Who said it first" |
| 10 | Friction & Ghosts | Silences, who broke them, breadcrumbs, conflict texting, pursuer–distancer episodes | Timeline of silence bars | "Ghost-busters" |
| 11 | The Storyboard | Weekly volume and reply time, with milestones as film frames; tapping a frame shows its masked excerpts (local only) | Line chart + frame strip | "Interval twist" markers |
| 12 | Director's Cut (what-if) | Sliders for reply speed, initiation share and follow-up questions; scores and tier recompute live | Sliders + live dials | Re-shoot your film |
| 13 | Texting Fingerprint | Generative abstract art seeded by the metric vector; identical chats give identical art | Canvas art, exportable | A one-of-a-kind print of your chat |
| 14 | The Narrative (optional) | AI film title, tagline, three acts, verdict, tips | Script typography | Typewriter reveal during the LLM wait |

The report ends with the share-banner builder and the "Take one for the gang" donation.

**What-if engine.** The sliders call a new C ABI function, `lm_score(handle, score_inputs_json)`, which runs only `ScorePolicy` on perturbed inputs (no re-parse), so each recompute fits inside one frame. It is labelled as a simulation, not advice.

**Look and feel.** Retro cinema: film grain, marquee bulbs, film-strip separators, VHS title cards, tier palettes from the archetype file, dark mode by default. Motion respects `prefers-reduced-motion`. Every chart has a text summary and a table fallback, colour is never the only signal, and contrast meets WCAG AA.

### `LocalReport` (what `lm_analyze` returns; never sent anywhere)

```ts
interface LocalReport {
  schema_version: "1.1";
  persona: "LAILA" | "MAJNU";
  span: { first_date: string; last_date: string; weeks: number; sessions: number; messages: number; trailer_mode: boolean };
  metrics: MetricsBlock;                       // same shape as AbridgedPayload.metrics
  confidence: Record<MetricId, { n: number; level: "low" | "medium" | "high"; lo?: number; hi?: number }>;
  tier: { id: TierId; majnu_meter: number; chemistry_score: number; plot_twist: boolean };
  weekly: WeeklyPoint[];
  monthly_initiation: { month: string; self: number; other: number }[];
  latency_hist: { self: number[]; other: number[] };        // 6 buckets
  heatmap: { self: number[]; other: number[] };             // 7 x 24, Monday-first, local hours
  ghosts: { week: number; days: number; broken_by: "SELF" | "OTHER" | null }[];
  top_emojis: { self: string[]; other: string[] };          // top 5 each
  lsm_categories: { name: string; self: number; other: number }[];
  milestones: LocalMilestone[];                             // with masked excerpts, for local display
  score_inputs: ScoreInputs;                                // what the what-if sliders perturb
  fingerprint_seed: string;                                 // hash of the metric vector
}
```

## Abridgment and token management

The daily token cap, not the per-minute cap, is the binding constraint: on Groq's free plan `openai/gpt-oss-120b` and `openai/gpt-oss-20b` each allow 30 RPM, 1K requests/day, 8K tokens/min and 200K tokens/day per organization ([Groq rate limits](https://console.groq.com/docs/rate-limits)). The engine caps the payload at 1,300 tokens with masked excerpts on by default, which buys about 105 narratives per model per day; everything in this section exists to make those tokens count.

### Pipeline inside the Wasm engine

1. **Sanitize.** Participant names and their name tokens become `[SELF]` / `[OTHER]`; phone numbers, emails, URLs, @handles, 6-digit PIN codes and any number of 4+ digits become `[PHONE]`, `[EMAIL]`, `[LINK]`, `[HANDLE]`, `[NUM]`. A small on-device first-name gazetteer masks third-party names as `[NAME]`. Masking runs before any text is eligible for an excerpt.
2. **Sessionize.** A new session starts after a gap of 240 minutes (configurable). A turn is a maximal run of consecutive messages from one sender inside a session.
3. **Compute metrics** per session and per ISO week, oriented by role (see Metric catalogue). These never need the LLM.
4. **Detect milestone candidates** from the weekly series and from discrete events.
5. **Score and select Top-N** under the token budget with a diversity penalty.
6. **Attach micro-excerpts** (masked, at most 4 per milestone, 80 characters each) and serialize the `AbridgedPayload`.
7. **Wipe.** `lm_close()` zeroes the arena holding raw text before freeing it.

### Metrics

The engine computes all 22 metrics and both headline scores (defined in the Metric catalogue) before milestone detection; milestones are scored on their weekly series.

### Milestone detection and scoring

Candidates come from two sources. **Change points**: for each weekly feature (volume, each side's median latency, initiation share, reciprocity, LSM), take the first difference and its robust z-score, z = (Δx − median(Δx)) / (1.4826 × MAD); any abs(z) > 2.5 marks the session where the shift begins. **Discrete events**: first session, last session, peak-volume session, longest silence and the session that ends it, each ghost event, and the first session after a ghost ("comeback").

Each candidate gets a salience score:

```latex
S_i = 0.40\,\min(|z_i|/4,\,1) + 0.30\,w_{\text{event}(i)} + 0.15\,r^{\text{vol}}_i + 0.15\,r^{\text{shift}}_i
```

where w is a fixed weight per event type, r^vol is the session's volume percentile and r^shift is its reciprocity-change percentile. Selection is greedy maximal marginal relevance with a token knapsack:

```latex
\text{next} = \arg\max_{i \notin \text{Sel}} \Big[\lambda S_i - (1-\lambda)\max_{j \in \text{Sel}} e^{-|t_i - t_j|/\tau}\Big] \quad \text{s.t. } \sum \text{cost} \le B
```

with λ = 0.7, τ = 14 days, B = 1,300 tokens, N ≤ 8. The first and last sessions are seeded into the selection when the budget allows, so the narrative always has a beginning and an end.

### Token estimation

The client cannot ship the model's tokenizer cheaply, so it over-estimates: est = ceil(ASCII bytes / 4) + non-ASCII codepoints + 2 × emoji. Devanagari and emoji-heavy chats therefore get fewer excerpts, never a blown budget. The server recounts with the real tokenizer and drops the lowest-scoring milestones if the estimate was wrong.

### Per-call budget

| Part | Tokens (approx.) | Note |
| --- | --- | --- |
| Static instructions + output schema | \~600 | Identical every call, placed first; cached tokens do not count toward Groq limits |
| Metrics block | \~250 | Numbers only |
| Milestones (≤ 8) with excerpts | ≤ 1,050 | Enforced by the knapsack above |
| Output: low-effort reasoning + JSON | ≤ 900 | `reasoning_effort: "low"`, `max_completion_tokens: 900`; reasoning tokens are still generated, so they are budgeted |

Counted per call ≈ 1,300 in + \~600 out ≈ 1,900 tokens → \~105 narratives/day and \~4/min per model. The fallback chain stretches that:

| Step | Provider and model | Narratives/day (approx.) |
| --- | --- | --- |
| 1 | Groq `openai/gpt-oss-120b` (best narrative quality) | \~105 |
| 2 | Groq `openai/gpt-oss-20b` | \~105 |
| 3 | Groq `qwen/qwen3.8-27b` | \~105 |
| 4 | Cloudflare Workers AI `@cf/meta/llama-3.1-8b-instruct`: 10,000 free neurons/day at 25,608 neurons per M input and 75,147 per M output tokens ≈ 78 neurons per call ([Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)) | \~125 |
| 5 | Metrics-only report | unlimited |

That is roughly 440 narratives a day at ₹0, before cache hits. Groq lists each model separately in its rate-limit table; confirm on the account's limits page that the buckets are per model before counting on steps 2–3. Model ids live in config, because both providers retire models.

### C++ signatures

```cpp
namespace lm::abridge {

enum class ExcerptMode : uint8_t { None, Masked };          // Masked is the default

struct EngineConfig {
  Role          role;
  ParticipantId self_id;
  int16_t  utc_offset_min_for_hours = 330;   // night-owl and rhythm metrics use local hours
  uint32_t session_gap_min    = 240;
  uint32_t max_milestones     = 8;
  uint32_t max_excerpts_each  = 4;
  uint32_t excerpt_max_chars  = 80;
  uint32_t token_budget       = 1300;
  float    mmr_lambda         = 0.7f;
  float    mmr_tau_days       = 14.f;
  float    z_threshold        = 2.5f;
  ExcerptMode excerpt_mode    = ExcerptMode::Masked;
};

struct Session   { uint32_t first_seq, last_seq; int64_t start_ms, end_ms; ParticipantId initiator, closer; bool late_night; };
struct Turn      { uint32_t first_seq, last_seq; ParticipantId sender; uint32_t chars; bool has_question, is_bid, is_dry; };

struct SideStats {                                   // one per participant, oriented SELF / OTHER
  double latency_p50_s, latency_p90_s;
  double initiation_share, msg_share, char_share;
  double double_text_rate, double_text_fast_share, double_text_slow_share;
  double turn_toward_rate, followup_q_rate, dry_reply_rate;
  double affection_rate, we_talk_rate, conflict_rate, night_share, emoji_density;
  uint32_t ghost_events, ghosts_broken, pd_episodes_started;
};

enum class Momentum : uint8_t { Fading, Steady, Rising };

struct PairStats {
  double lsm, length_mirroring, emoji_mirroring, rhythm_overlap, shared_laughter;
  double reciprocity, latency_trend_s_per_week, fast_start_fade, hinglish_share;
  uint32_t longest_rally, breadcrumb_events;
  int8_t   first_affection_side;                     // -1 none, 0 SELF, 1 OTHER
  int16_t  first_affection_week;
  Momentum momentum;
  uint8_t  majnu_meter, chemistry_score;             // 0-100, see Metric catalogue
};

struct MetricsReport {
  SideStats self, other;
  PairStats pair;
  uint32_t sessions, messages, weeks;
  bool     trailer_mode;                             // < 300 messages or < 14 days
  ParserCapabilities caps;
};

struct WeeklyPoint { int32_t week; uint32_t msgs; double lat_self_p50, lat_other_p50, init_share, reciprocity, lsm, affection; };

enum class MilestoneType : uint8_t {
  First, Last, PeakVolume, LongestSilence, Comeback, Ghost, LatencyShift,
  EffortFlip, MirroringShift, FirstAffection, LongestRally, PursuerDistancerBurst
};
struct MilestoneCandidate { MilestoneType type; uint32_t session_idx; float z, salience; };
struct Excerpt   { ParticipantId speaker; int32_t dt_s; std::string masked_text; };
struct Milestone { MilestoneCandidate c; int32_t week; std::vector<Excerpt> excerpts; uint32_t est_tokens; };

class ILexicon {                                     // versioned JSON asset, English + Hinglish
 public:
  virtual ~ILexicon() = default;
  virtual bool is_filler(std::string_view token) const noexcept = 0;
  virtual bool in_category(std::string_view token, LexCategory c) const noexcept = 0;
  virtual bool is_hinglish(std::string_view message) const noexcept = 0;
};
class ISanitizer {
 public:
  virtual ~ISanitizer() = default;
  virtual std::string mask(std::string_view text, const MaskContext& ctx) const = 0;  // pure
};
class ITokenEstimator {
 public:
  virtual ~ITokenEstimator() = default;
  virtual uint32_t estimate(std::string_view utf8) const noexcept = 0;               // must over-estimate
};
class IMilestoneDetector {
 public:
  virtual ~IMilestoneDetector() = default;
  virtual std::vector<MilestoneCandidate> detect(std::span<const WeeklyPoint>, std::span<const Session>,
                                                 const MetricsReport&, const EngineConfig&) const = 0;
};

class Sessionizer {
 public:
  std::vector<Session> sessions(std::span<const MessageEvent>, const EngineConfig&) const;
  std::vector<Turn>    turns(std::span<const MessageEvent>, const Session&, const ILexicon&) const;
};
class MetricEngine {
 public:
  explicit MetricEngine(const ILexicon& lex);
  MetricsReport            compute(const ChatLog&, std::span<const Session>, const EngineConfig&) const;
  std::vector<WeeklyPoint> weekly (const ChatLog&, std::span<const Session>, const EngineConfig&) const;
};
class ScorePolicy {                                  // Majnu Meter + Chemistry; weights from metric_policy JSON
 public:
  explicit ScorePolicy(std::string_view policy_json);
  void apply(MetricsReport& r) const;
};
class MilestoneSelector {
 public:
  std::vector<Milestone> select(std::vector<MilestoneCandidate> cands, const ChatLog&, std::span<const Session>,
                                const ISanitizer&, const ITokenEstimator&, const EngineConfig&) const;
};

// Facade. LocalReport stays on the device; only AbridgedPayload may cross the network.
class AbridgmentEngine {
 public:
  AbridgmentEngine(EngineConfig cfg, std::unique_ptr<ILexicon>, std::unique_ptr<ISanitizer>,
                   std::unique_ptr<ITokenEstimator>, std::unique_ptr<IMilestoneDetector>, ScorePolicy);
  LocalReport     analyze(const ChatLog& log);
  AbridgedPayload abridge(const LocalReport& report) const;
};

}  // namespace lm::abridge

// Wasm boundary: plain C ABI, JSON strings in and out, run inside a Web Worker
extern "C" {
  lm_handle*  lm_open(const uint8_t* bytes, size_t len, const char* parse_ctx_json);
  const char* lm_participants(lm_handle*);                         // for "which one is you?"
  const char* lm_analyze(lm_handle*, const char* engine_cfg_json); // LocalReport JSON
  const char* lm_abridge(lm_handle*);                              // AbridgedPayload JSON
  void        lm_close(lm_handle*);                                // zeroes arena, then frees
}
```

## DTOs and data schemas

Three DTOs cross the network, and none carries a name, a date or raw text: `AbridgedPayload` (client → server), `AnalysisResult` (server → client) and the opt-in `DonationRecord`. Time is expressed as week offsets from the first message, because absolute dates plus message counts are a re-identification key.

### Endpoints

| Method | Path | Body in | Body out | Limits |
| --- | --- | --- | --- | --- |
| POST | `/v1/analyze` | `AbridgedPayload` | `AnalysisResult` | 16 KB body; 10 req/min per IP; idempotent on `request_id` |
| POST | `/v1/donations` | `DonationRecord` | `{donation_id, receipt_token}` | 8 KB body; separate consent required |
| DELETE | `/v1/donations/{donation_id}` | header `X-Receipt-Token` | 204 | Lets a donor withdraw later |
| GET | `/v1/policy` | — | tier thresholds + `metric_policy_version` | Cached by the client for offline tier display |
| GET | `/v1/health` | — | provider quota status | Lets the UI warn "narratives are busy, metrics still work" |

### `AbridgedPayload` v1 (client → `/v1/analyze`)

```json
{
  "schema_version": "1.1",
  "engine_version": "0.1.0",
  "metric_policy_version": "2026-10-21",
  "request_id": "9b2f4c1e-7a35-4e0b-9d61-2f3c8a7e5b10",
  "role": "MAJNU",
  "platform": "whatsapp",
  "capabilities": { "reactions": false, "seconds_precision": false, "edit_markers": true, "explicit_timezone": false },
  "span": { "weeks": 31, "sessions": 148, "messages": 9412, "trailer_mode": false },
  "language": { "hinglish_share": 0.62 },
  "metrics": {
    "self": {
      "latency_p50_s": 140, "latency_p90_s": 2100, "initiation_share": 0.71, "msg_share": 0.63, "char_share": 0.68,
      "double_text_rate": 0.18, "double_text_fast_share": 0.7, "turn_toward_rate": 0.88, "followup_q_rate": 0.21,
      "dry_reply_rate": 0.05, "affection_rate": 3.1, "we_talk_rate": 4.2, "conflict_rate": 0.6, "night_share": 0.22,
      "ghost_events": 1, "ghosts_broken": 4, "pd_episodes_started": 6
    },
    "other": {
      "latency_p50_s": 960, "latency_p90_s": 14400, "initiation_share": 0.29, "msg_share": 0.37, "char_share": 0.32,
      "double_text_rate": 0.04, "double_text_fast_share": 0.2, "turn_toward_rate": 0.61, "followup_q_rate": 0.07,
      "dry_reply_rate": 0.24, "affection_rate": 1.2, "we_talk_rate": 1.9, "conflict_rate": 0.3, "night_share": 0.18,
      "ghost_events": 4, "ghosts_broken": 1, "pd_episodes_started": 1
    },
    "pair": {
      "majnu_meter": 71, "chemistry_score": 58, "lsm": 0.81, "length_mirroring": 0.34, "emoji_mirroring": 0.27,
      "rhythm_overlap": 0.66, "shared_laughter": 0.38, "reciprocity": 0.62, "longest_rally": 42,
      "breadcrumb_events": 2, "first_affection": { "side": "SELF", "week": 6 }, "momentum": "FADING",
      "fast_start_fade": 0.45, "latency_trend_s_per_week": 41.5
    }
  },
  "milestones": [
    {
      "id": "m1",
      "type": "LATENCY_SHIFT",
      "week": 9,
      "z": -3.1,
      "salience": 0.82,
      "session": { "duration_min": 94, "msgs_self": 31, "msgs_other": 12, "initiator": "SELF", "closer": "OTHER", "late_night": true },
      "excerpts": [
        { "speaker": "SELF",  "dt_s": 0,    "text": "kal [NAME] ki party mein aa rahi ho?" },
        { "speaker": "OTHER", "dt_s": 5400, "text": "dekhti hoon" }
      ]
    }
  ],
  "excerpt_mode": "masked",
  "est_tokens": 1240
}
```

`role` carries the persona (`LAILA` | `MAJNU`) and only affects narrative grammar; the user is always the chaser.

Server-side validation (Pydantic, `extra="forbid"`), each failure a 422 with a stable error code:

| Field | Rule |
| --- | --- |
| `schema_version` | major must be `1` |
| `role` | `MAJNU` \| `LAILA` |
| `platform` | `whatsapp` \| `instagram` |
| shares, rates in 0–1, `lsm`, `reciprocity`, `hinglish_share` | 0.0–1.0 |
| `affection_rate`, `conflict_rate` (per 100 msgs), `we_talk_rate` (per 1,000 words) | ≥ 0, ≤ 100 |
| `majnu_meter`, `chemistry_score` | integer 0–100 |
| `momentum` | `RISING` \| `STEADY` \| `FADING` |
| `milestones` | ≤ 8; `type` from the fixed enum; `week` within `span.weeks`; none when `trailer_mode` |
| `excerpts` | ≤ 4 per milestone; `text` ≤ 80 chars; empty when `excerpt_mode = none` |
| every `text` | server re-runs the PII patterns (phone, email, URL, handle, 4+ digit number); any hit → 422 `PII_DETECTED`, nothing is forwarded |
| whole body | ≤ 16 KB; server token recount ≤ 1,400, else lowest-salience milestones dropped |

### `AnalysisResult` (server → client)

```json
{
  "schema_version": "1.1",
  "request_id": "9b2f4c1e-7a35-4e0b-9d61-2f3c8a7e5b10",
  "status": "complete",
  "degraded_reason": null,
  "tier": { "id": "Tier_04", "majnu_meter": 71, "chemistry_score": 58, "policy_version": "2026-10-21" },
  "narrative": {
    "language": "hinglish",
    "film_title": "Ek Tarfa Express",
    "tagline": "Tum reply karte rahe, woh 'dekhti hoon' karti rahi",
    "acts": [
      { "act": 1, "title": "Meet-cute", "text": "Pehle 8 hafte: 2 AM rallies of 40+ messages, and you said ❤️ first in week 6 ..." },
      { "act": 2, "title": "Interval twist", "text": "Week 9 changed the background score: their replies went from minutes to hours ..." },
      { "act": 3, "title": "Now showing", "text": "You still start 7 of 10 chats. They turn toward 61% of your bids ..." }
    ],
    "dynamics": { "chaser": "SELF", "momentum": "FADING", "confidence": 0.7 },
    "milestone_notes": [ { "id": "m1", "caption": "Week 9: replies went from minutes to hours" } ],
    "verdict": "Strong opening, slow second half. Let them write the next scene.",
    "advice": [ "Let them start the next few conversations.", "Ask one follow-up question about something they said." ],
    "flags": { "boundary_signal": false }
  },
  "provider": { "name": "groq", "model": "openai/gpt-oss-120b", "latency_ms": 1100, "tokens_in": 1290, "tokens_out": 610 }
}
```

`status` is `complete` or `degraded`. When degraded (`rate_limited`, `provider_error`, `schema_invalid`), `narrative` is `null` but `tier` is still present, because the tier is a pure function of the metrics (`TierPolicy`, server-side Python, thresholds served at `/v1/policy`). The LLM never chooses the tier.

`flags.boundary_signal` is true when the excerpts show the other person asking for space or to stop contact. The UI then suppresses the share banner and shows a respectful message instead. For a product whose role name means "madly chasing", this guardrail is worth having before a panel asks.

### LLM output contract (strict structured output)

`gpt-oss-120b` and `gpt-oss-20b` on Groq support `json_schema` with `strict: true` (constrained decoding: every field required, `additionalProperties: false`, nullables as unions) ([Groq structured outputs](https://console.groq.com/docs/structured-outputs)). Qwen and Workers AI use best-effort JSON mode, so the server validates and repairs once before falling through. The `narrative` object above is that schema, defined once in Pydantic:

```python
class Dynamics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chaser: Literal["SELF", "OTHER", "BALANCED"]
    momentum: Literal["RISING", "STEADY", "FADING"]
    confidence: float = Field(ge=0, le=1)

class Act(BaseModel):
    model_config = ConfigDict(extra="forbid")
    act: Literal[1, 2, 3]
    title: str = Field(max_length=30)
    text: str = Field(max_length=420)

class MilestoneNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^m[1-8]$")
    caption: str = Field(max_length=90)

class Flags(BaseModel):
    model_config = ConfigDict(extra="forbid")
    boundary_signal: bool

class Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["english", "hinglish"]
    film_title: str = Field(max_length=40)
    tagline: str = Field(max_length=90)
    acts: list[Act] = Field(min_length=3, max_length=3)
    dynamics: Dynamics
    milestone_notes: list[MilestoneNote] = Field(max_length=8)
    verdict: str = Field(max_length=140)
    advice: list[str] = Field(max_length=3)
    flags: Flags
```

The server still validates the reply (length limits are not all enforceable by constrained decoding) and rejects any `milestone_notes.id` that was not in the request.

**Narrative prompt rules** (versioned `prompts/narrative_v1.md`, static prefix first so Groq can cache it):

- Voice: a Bollywood-trailer narrator, warm and teasing, never cruel. Write in Hinglish when `hinglish_share` ≥ 0.4, otherwise English.
- Three acts mapped to milestones; every claim cites a number or milestone from the payload. Never invent quotes, events or numbers.
- Quote at most one excerpt, and only as given.
- Never diagnose (no "anxious attachment", "narcissist"), never use gender stereotypes, never suggest manipulation (jealousy plays, games, timed silences).
- If the excerpts show the other person asking for space or to stop, set `boundary_signal`, drop the jokes, and advise respecting it.
- Advice is concrete and grounded in the metrics (e.g. "ask one follow-up question" when `followup_q_rate` is low).

### `DonationRecord` (opt-in, `/v1/donations`)

```json
{
  "schema_version": "1.1",
  "consent": { "text_version": "2026-10-21", "month": "2026-10", "scope": ["metrics", "weekly_series", "milestone_features"], "excerpts_included": false },
  "role": "MAJNU",
  "platform": "whatsapp",
  "pairing": "UNDISCLOSED",
  "metrics": { "self": { "...": "same shape as AbridgedPayload" }, "other": { }, "pair": { } },
  "weekly": [[52, 120, 600, 0.7, 0.66, 0.8], [61, 140, 900, 0.75, 0.6, 0.4]],
  "milestones": [ { "type": "LATENCY_SHIFT", "week": 9, "z": -3.1, "salience": 0.82 } ],
  "labels": { "tier": "Tier_04", "self_reported_outcome": "FRIENDS" }
}
```

`weekly` rows are `[msgs, latency_self_p50_s, latency_other_p50_s, initiation_share, reciprocity, affection]`, capped at 104 weeks. `pairing` (`M_F` | `F_M` | `SAME` | `UNDISCLOSED`, default `UNDISCLOSED`) is optional and self-reported. `self_reported_outcome` (`TOGETHER` | `FRIENDS` | `NO_CONTACT` | `UNKNOWN`) is one tap on the exit screen and is the label that makes the pool useful. The record is never linked to `request_id`, IP or user agent; the server stores only the month. Records are sealed into batches of 50 (configurable up to 100) by a scheduled job.

### Client-only view model: `ShareCard`

The banner is drawn on a `<canvas>` in the browser, so serving it costs nothing: `{tier_id, archetype_title, film_title, tagline, three_stats: [{label, value}], theme}` in two sizes, 1080 × 1920 (stories) and 1080 × 1080. The three stats default to Majnu Meter, Chemistry Score and Longest rally, and the user can swap them. Tier → archetype mapping is a static JSON asset, so Bollywood/Hollywood names can change without a deploy. The card never shows the other person's name or words, and is suppressed when `boundary_signal` is true.

## Deployment: the ₹0 stack

Every component runs on a free tier that needs no card, and the only cold start a user can feel (the Python API) is hidden by a pre-warm ping sent when the landing page opens.

| Component | Service | Free limits that matter | Cold start / sleep |
| --- | --- | --- | --- |
| Frontend + Wasm (static) | Cloudflare Workers static assets | Requests to static assets are free and unlimited ([Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)) | None, served from the CDN |
| API (FastAPI) | Vercel Hobby, Python runtime, Fluid compute | 1M invocations, 4 active-CPU hours/month; time spent waiting on the LLM is not billed as active CPU; personal/non-commercial use only; the project pauses if limits are exceeded ([Vercel limits](https://vercel.com/docs/limits)) | Archived functions add at least 1 s on first call ([Vercel runtimes](https://vercel.com/docs/functions/runtimes)); hidden by the pre-warm |
| LLM primary | Groq free plan | Per model: 30 RPM, 1K RPD, 8K TPM, 200K TPD; inputs not retained by default, Zero Data Retention available ([Groq: Your Data](https://console.groq.com/docs/your-data)) | None |
| LLM fallback | Cloudflare Workers AI (REST) | 10,000 neurons/day ([Workers AI pricing](https://developers.cloudflare.com/workers-ai/platform/pricing/)) | None |
| Donations database | Neon Free Postgres | 0.5 GB storage, 100 CU-hours/month; compute scales to zero after 5 min ([Neon pricing](https://neon.com/pricing)) | Wakes in a few hundred ms ([Neon FAQ](https://neon.com/faqs/best-free-low-cost-managed-postgres-services)); only donation writes touch it |
| Cache + rate limits | Upstash Redis Free | 256 MB, 500,000 commands/month ([Upstash](https://upstash.com/blog/upstash-vs-aws-elasticache-serverless-redis-pricing-and-performance-2026)) | None (HTTP API) |
| Bot check | Cloudflare Turnstile | Free | None |
| Batch sealing | GitHub Actions scheduled workflow | Free minutes on the repo's plan | n/a |

**Headroom.** At \~20 ms active CPU per `/v1/analyze`, 4 CPU-hours covers \~720,000 calls a month, so Vercel is not the bottleneck; the LLM chain is (\~440 narratives/day). At \~6 Redis commands per analysis, Upstash covers \~80,000 analyses a month. At \~2 KB per donation, Neon's 0.5 GB holds \~250,000 donations.

**Pre-warm.** The landing page fires `GET /v1/health` in the background. The user then spends 30 s or more choosing a role, exporting and reviewing local results, so the function is warm by the time they press send. `/v1/health` also reports quota state so the UI can say "narratives are busy, your report still works".

**Wiring.** The static site and API live on different origins, so the API allows CORS only from the site's exact origin. Secrets (`GROQ_API_KEY`, `CF_ACCOUNT_ID`, `CF_AI_TOKEN`, `DATABASE_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `TURNSTILE_SECRET`) live only in Vercel environment variables.

### Options rejected

| Option | Why not |
| --- | --- |
| Cloudflare Python Workers (free) | 10 ms CPU per request on the free plan, and \~1 s Python cold start ([Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/), [Cloudflare changelog](https://developers.cloudflare.com/changelog/22/)) |
| Render free web service | Spins down after 15 min idle and takes 30–60 s to wake ([comparison](https://www.techplained.com/best-free-hosting)) |
| Supabase free | Projects auto-pause after a week of inactivity ([comparison](https://ecorpit.com/neon-vs-supabase-serverless-postgres-saas-backend-2026/)) |
| Cerebras free trial | Needs a payment method before API access ([BenchLM, read 14 Sep 2026](https://benchlm.ai/md/free-tier/cerebras.md)) |
| Google Gemini free tier | Free-tier prompts may be used to improve Google's products, which conflicts with sending chat excerpts ([free LLM API list](https://github.com/mnfst/awesome-free-llm-apis/wiki)) |

## Quality bars: accurate, robust, secure, fast

Every bar below is a number that a test or CI gate enforces, so "accurate, robust, secure and fast" can be checked rather than claimed.

### Accuracy

| Area | Target | Enforced by |
| --- | --- | --- |
| Parsing | 100% of messages, senders and UTC timestamps correct on the fixture corpus; ≥ 99.5% on real anonymized exports (200-message manual spot check each) | Golden tests; spot-check log in `docs/` |
| Date order | Correct on every fixture, including ambiguous DMY/MDY files; still-ambiguous files ask the user | Unit tests |
| Sanitizer | ≥ 99% recall on a labelled Indian PII set: +91 and 10-digit phones in spaced/dashed forms, emails, UPI IDs (`name@okaxis`), 12-digit Aadhaar-like numbers, PAN-like codes, @handles, URLs, PIN codes; zero leaks of participant names or the canary | Labelled test set in CI; adds `[UPI]` and `[ID]` tokens |
| Metrics | Each of the 22 has hand-computed unit tests on tiny chats; property tests: swapping SELF/OTHER mirrors paired metrics, shifting all timestamps changes nothing, reordering equal-timestamp messages changes nothing | Catch2 + property tests |
| Cross-build determinism | Native and Wasm builds produce the same `LocalReport` on every fixture (floats equal to 1e-9; fixed summation order) | CI job diffs both outputs |
| Confidence | Seeded bootstrap ranges; low-sample cards flagged | Golden tests |
| Narrative faithfulness | Every number in the narrative must appear in the payload (after rounding), every milestone id must exist, and no excerpt may be quoted that was not sent; failures trigger one retry, then the next provider | Server-side fact-check gate + tests |
| Narrative quality | 20 synthetic payloads scored on a written rubric (tone, accuracy, no stereotypes, Hinglish grammar) before launch and after any prompt change | Manual review checklist |

### Robustness

- **Fuzzing:** libFuzzer on every parser natively; 5 minutes per parser on each push to `main`, longer runs nightly. Any crash, hang or sanitizer report fails the build (ASan and UBSan on in test builds).
- **Input limits:** 50 MB upload, 200,000 messages, 256 MB Wasm memory ceiling, 30 s worker timeout with a Cancel button.
- **Fail-soft metrics:** each metric computes independently; one failure marks that card "unavailable" with a reason code and the rest of the report still renders.
- **Error taxonomy:** `ParseCode`, `EngineCode` and API error codes map to friendly English and Hinglish messages; nothing shows a stack trace.
- **API resilience:** timeouts of 15 s per Groq call and 20 s for Workers AI inside a 25 s total budget; a per-provider circuit breaker in Redis (opens after 3 consecutive 429/5xx, for 60 s); a `429` moves to the next provider instead of retrying; idempotency on `request_id` for 24 h. If Redis or Neon is down, `/v1/analyze` still works uncached and donations return 503 "try later".
- **Versioning:** the server accepts the current and previous minor `schema_version`; `engine_version` and `metric_policy_version` travel with every payload.

### Security

- **Content Security Policy on the web app:** `default-src 'self'`; `script-src 'self' 'wasm-unsafe-eval' https://challenges.cloudflare.com`; `connect-src 'self'` plus the API origin; `frame-src https://challenges.cloudflare.com`; `object-src 'none'`; `base-uri 'none'`; Trusted Types on; no inline scripts. Also HSTS, `Referrer-Policy: no-referrer` and a minimal `Permissions-Policy`.
- **XSS:** LLM output and every chat-derived string render as text only; no `dangerouslySetInnerHTML` anywhere (lint rule).
- **Local data:** nothing is persisted by default; the only stored item is the donation receipt token; "Delete everything" clears memory and storage.
- **API surface:** body size checked before parsing, JSON depth ≤ 8, Pydantic strict types, Turnstile token verified server-side, per-IP and per-token rate limits, exact-origin CORS, no cookies (so no CSRF surface), generic error bodies.
- **Least privilege:** the Cloudflare token is scoped to Workers AI only; the Neon role can only insert donations and delete by id with a matching receipt hash; receipt tokens are stored as SHA-256 hashes.
- **Supply chain:** lockfiles, Dependabot, `pip-audit` and `npm audit` in CI, CodeQL and secret scanning on GitHub, Actions pinned by commit SHA.
- **Privacy tests:** the end-to-end canary test (no canary, name or unknown key in any request body) and a log-scanner test that fails if any request body content reaches logs.

### Speed

| Budget | Target |
| --- | --- |
| Landing page first contentful paint, mid-range Android on 4G | < 1.5 s |
| Initial JavaScript | < 150 KB gzipped; the Wasm engine (< 1 MB gzipped) loads lazily with `instantiateStreaming` once the user reaches the role screen |
| Parse + analyze 50,000 messages | < 2 s desktop, < 5 s low-end Android |
| First report scene | < 300 ms after analysis |
| What-if recompute | < 16 ms (one frame) |
| `/v1/analyze` p95 | < 6 s including the LLM; Groq structured outputs cannot stream ([Groq structured outputs](https://console.groq.com/docs/structured-outputs)), so the typewriter loading scene covers the wait |
| `/v1/analyze` cache hit | < 300 ms |

How: one-pass parsers over `string_view`, arena allocation, lexicons compiled to sorted arrays with binary search, transferable `ArrayBuffer`s into the worker, streaming unzip, scenes rendered lazily as they scroll into view, Brotli from the CDN, and the API pre-warm ping.

## Privacy, consent and legal posture

The hardest panel question will not be technical: every chat contains a second person who never agreed to be analyzed, and the donation pool turns that into a dataset. The design answers it by keeping raw text on-device, sending only masked micro-excerpts for the narrative, and excluding all text from donations. This is an engineering position, not legal advice; get the university's ethics committee and legal office to sign off before collecting donations.

**India's DPDP regime is now live in phases.** The DPDP Rules, 2025 were notified in November 2025 with a three-phase rollout; the notice, verifiable-consent, security and breach obligations commence 18 months after publication ([DSK Legal summary](https://dsklegal.com/?p=26455), [PIB note](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf)). Design to those obligations now so the app does not need a rewrite in May 2027.

| Concern | Design response |
| --- | --- |
| The crush's data | Raw chat never leaves the device. The payload carries `SELF`/`OTHER`, week offsets and ≤ 32 masked excerpts of ≤ 80 chars. Donations carry no text at all. |
| Age | **18+ only (decided).** A self-declared age gate before upload, stating the app is not for minors; no ID is collected. DPDP treats under-18s as children needing verifiable parental consent, which excluding them avoids. |
| Consent | Two separate, unticked consents: (1) send the abridged payload for a narrative, after a "see exactly what we send" preview; (2) donate. Both versioned (`consent.text_version`). |
| Withdrawal | Donation returns a `receipt_token` stored locally; `DELETE /v1/donations/{id}` removes the record until its batch is sealed. |
| Inference providers | Groq does not retain inference inputs/outputs by default but may log them for up to 30 days for reliability or abuse investigation; Zero Data Retention can be switched on by any customer; stored data sits in US GCP ([Groq: Your Data](https://console.groq.com/docs/your-data)). Turn ZDR on and state the US transfer in the notice. Review Cloudflare's Workers AI data terms before enabling the fallback; it is a config switch. |
| Gender data | Optional, self-reported, donations only, default `UNDISCLOSED`, never used in scoring. |
| Server logs | Never log request bodies. Log `request_id`, status code, token counts, latency, provider. No IP in the donation table. |
| Research use of the pool | Treat as human-subjects research: ethics approval before any analysis or model training on donations. |

### Threat model

| Threat | Mitigation |
| --- | --- |
| Modified client sends raw text in excerpts | Count and length caps, PII re-scan, 16 KB body cap, `extra="forbid"` |
| Prompt injection inside excerpts ("ignore previous instructions") | Excerpts are passed as JSON data in a delimited block; strict output schema means an attack can only change capped strings; server rejects unknown milestone ids |
| Bots burning the free quota | Per-IP rate limit, a free bot check (e.g. Cloudflare Turnstile) on `/v1/analyze`, cache by payload hash |
| API key leakage | Provider keys live only in server env vars; the browser never calls the LLM directly |
| Donation poisoning | Plausibility checks (shares sum to \~1, latencies non-negative, week counts consistent), per-IP caps, dedupe on a hash of the metric vector |
| Re-identification from donations | No dates, no names, month-level timestamps, no link to the analysis request |

## Risks, open questions and decisions

The biggest risk is depending on one free provider's terms, which already changed once this year; the inference adapter, model rotation and metrics-only fallback exist for that reason.

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Free model retired or limits cut (happened 16 Aug 2026) | Narratives stop | Five-step fallback chain; model ids in config; metrics-only degrade |
| \~440 narratives/day ceiling on a viral day | Users see "busy" | Cache by payload hash, client keeps the payload and retries later; report and share card never block on the LLM |
| Groq quota buckets turn out to be shared across models | Capacity drops to \~230/day | Verify on the limits page during Phase 5; chain still degrades cleanly |
| Vercel Hobby is non-commercial and pauses on overrun | API offline | University project fits the terms; CPU headroom is \~7× expected load; monetizing means moving the API first |
| Export formats drift between app versions | Parse failures | Fixture corpus in CI, sniff threshold, anonymous `ParseCode` counters |
| Masking misses a third-party name | Name reaches the provider | Gazetteer + server re-scan + payload preview; `excerpt_mode = none` available |
| Hinglish lexicons miss slang | Metrics under-count | Versioned lexicon JSON with spelling variants; fixtures include Hinglish chats; easy to extend |
| Low-end Android performance | Slow or crashed tab | Web Worker, streaming parse, 200K message cap, no `std::regex`, `-Oz`; targets to verify: Wasm < 1 MB gzipped, 50K messages in < 2 s on a mid-range phone |
| "Is a chemistry score scientific?" | Panel credibility | Published formulas, research table, descriptive framing; calibrate weights on donated outcomes before making predictive claims |

### Still open

Technical decisions are closed; these remain, none of which blocks Phases 1–5:

- [ ] Archetype names, taglines and poster art for all 20 entries (design review; your approval per entry).
- [ ] University legal office review of the final archetype names.
- [ ] App name and domain (the API needs the site's exact origin for CORS).
- [ ] Ethics committee approval before the first donation batch is analyzed.
- [ ] Confirm per-model Groq buckets on the account's limits page.

### Build plan

Each phase ends with green tests and a review stop; the same phases drive `prompt.md` for Claude Code.

1. **Scaffold:** monorepo, JSON Schemas as the single source of truth with generated Pydantic and TypeScript types, CI, fixture generator and corpus, PII test set.
2. **Parsers:** `IChatParser`, WhatsApp Android/iOS and Instagram strategies, registry, timezone resolver, fuzzers.
3. **Metrics and scores:** lexicons, sessionizer, the 22 metrics, confidence, `ScorePolicy`, tier policy, `lm_score`; golden and property tests; native-vs-Wasm determinism job.
4. **Abridgment and Wasm:** sanitizer, milestones, Top-N selector, token estimator, Emscripten build, Web Worker bridge.
5. **Web app, local-only:** onboarding with persona picker, 18+ gate, export guides, the 14-scene Film Report, share canvas, all with DRAFT archetypes.
6. **Design review (your gate):** archetype names, taglines, poster art, insight copy; you approve entries in `archetypes.json`.
7. **API and inference:** FastAPI on Vercel, validation, PII re-scan, fallback chain, fact-check gate, cache, rate limits, Turnstile, pre-warm, payload preview and consent.
8. **Donations:** consent flow, `/v1/donations`, receipt-token delete, batch sealing at 50.
9. **Hardening and launch:** every quality bar green, low-end phone pass, accessibility, privacy review, a load test within free limits, production build gate (all archetypes approved).

## Appendix: v1 feature list (final, 21 Oct 2026)

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

**Out of scope for v1:** group chats; Telegram or Snapchat; accounts or login; server-side history; comparing multiple crushes; push notifications; paid features; Devanagari Hindi and other Indian languages; installable app; percentile comparison with the donation pool (needs pool data first).
