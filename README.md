# WuwaSchool · 呜哇校园

> A terminal-based slice-of-life campus sim, fan-made for **Wuthering Waves**.
> Press **Enter** to advance one day: wake up and refill stamina, hit a random
> event, run into someone, then watch the affinity deltas roll by.
> Characters, events and ending chains are all **plain JSON sitting next to the
> script** — drop a file into `mods/` and it's content.

```
❤ HP 87   ⚡STA 93/93   🌀STR 12    📅 Day 14 · Wed · Term 2 · Autumn
────────────────────────────────────────
  ▸ Jinhsi · Walking Side by Side Lv.3  ████████░░░░ +9
  ▸ Verina · Greenhouse Regular          ████░░░░░░░░ +3
  ▸ Sanhua · Dojo Rival                  ██████░░░░░░ +1
```

---

## Contents

- [Quick start](#quick-start)
- [Commands](#commands)
- [Core rules: HP / STA / STR / affinity](#core-rules)
- [Weekend getaway board](#weekend-getaway-board)
- [Event chains & personal endings](#event-chains--personal-endings)
- [File layout](#file-layout)
- [Modding (important)](#modding-important)
- [Saving & loading](#saving--loading)
- [Chain visualiser](#chain-visualiser)
- [Writing your own content: minimal template](#writing-your-own-content-minimal-template)
- [Reference: field glossary](#reference-field-glossary)
- [FAQ](#faq)

---

## Quick start

```bash
python3 wuwa_school.py
```

- **Requires Python 3.9+, standard library only.** Nothing to `pip install`.
- *(Optional)* install [Graphviz](https://graphviz.org/) if you want the
  `graph` command to emit a real PNG. Without it, the game degrades gracefully
  to an ASCII text chart and is otherwise unaffected.

At the title screen: `1` New Game · `2` Load Save · `3` Mod format help.

---

## Commands

Type any of these **at any prompt** (case-insensitive):

| Command | Effect |
|---|---|
| <kbd>Enter</kbd> | Advance one day. If an event fires, a choice is picked at random — perfect for idle grinding. |
| `1` / `2` / `3`… | Manually pick an option during an event or the weekend board. |
| `save` | Write a save immediately (day, stats, affinity, flags, active/clear chains, RNG seed). |
| `quit` / `q` | Exit. Unsaved progress for the current day is lost. |
| `status` / `s` | Dump state: three stats, every character's affinity + stage, mod counts, unlocked chains. |
| `graph` / `g` | Export the chain graph to `graphs/event_chain.png` (text chart if no Graphviz). |
| `reload` / `mod` | **Hot-rescan `mods/`** — new/changed content is picked up without a restart. |
| `help` / `h` | Print the command table. |

---

## Core rules

| Stat | Range | Meaning | How it moves |
|---|---|---|---|
| ❤ **HP** | 0–100 | Physical condition. Also caps your stamina ceiling. | Drops from pulling all-nighters, tough spars, cram school. Rises at the infirmary, rooftop, sleep. |
| ⚡ **STA** (stamina) | 0–`max` | How much you can push today. | Refilled to `max` at dawn. Spent by choices and weekend plans. |
| 🌀 **STR** (stress) | 0–100 | Too high and you sleep badly. | Cramming and being called on raise it; library, rooftop and the greenhouse lower it. |

### Stamina scales with HP — this is the whole point

```
STA max   = 50 + HP × 0.5          (HP 87 → 93 ; HP 40 → 70)
night rec = 6 + (HP − 50)/100 × 8 − STR/100 × 5    (floored at −3)
morning   = STR − 4
```

At HP 87 / STR 12 you wake up about **+9 HP**. Push HP down to 40 and the
same night is **−2 HP** — and you also lose access to stamina-heavy options
like Sanhua's dojo. **Don't stack late nights.**

### Affinity stages

These are computed automatically from the score; there is nothing to configure.

```
 0–19  Strangers passing by
 20–39 Nodding acquaintances
 40–59 Walking home together
 60–84 An open secret
 85+   The story is almost written
```

A personal ending can only close once the character is at **stage 85+**. Daily
changes are printed together at the end of the day, with `+ / −` and a bar.

---

## Weekend getaway board

On **Saturday and Sunday** the normal encounter pool is replaced by a pick-your-
own-plan board. Cost is paid up front; unaffordable plans are hidden.

| Plan | Gain | Cost | Notes |
|---|---|---|---|
| 📚 Library · grind the error notebook | `@all` +2 aff, HP +4, STR −8 | STA 12, STR +10 | Safe, boring, always there. |
| 🌤 Rooftop · stolen lunch break | HP +10, STR −14 | STA 6 | Best pure recovery. |
| 📝 Cram school · last seat by the door | `@all` −1 aff, STR −4 | STA 20, STR +14 | Buys grades with your face. |
| 🥋 Dojo · spar a set with Sanhua | Sanhua +6, HP −2 | STA 34, HP +4 | Hidden when STA can't cover it. |
| 🌱 Greenhouse · repot with Verina | Verina +6, HP +8, STR −10 | STA 16 | |
| 📻 Broadcast room ·秧秧's lunch request show | 秧秧 +5, STR −6 | STA 8 | |
| 💊 Infirmary · Baizhi's mandatory rest | Baizhi +4, HP +22, STR −12 | STA 4 | |
| 🌊 Riverside walk · after school | HP +6, STR −8, then a random encounter | STA 10 | |

End-of-day still prints the before/after of HP, STA and STR.

---

## Event chains & personal endings

A chain is an **ordered list of nodes**. The order lives in `chains.json`; the
text and choices for each node live in `chain_events.json`.

```
changli_main:  [cl_c1] ──▶ [cl_c2] ──▶ [cl_c3] ──▶ 🏁 The Unsigned Painting
jinhsi:        [jx_c1] ──▶ [jx_c2] ──▶ [jx_c3] ──▶ 🏁 The Tide Remembers You
sanhua:        [sh_c1] ──▶ [sh_c2] ──▶ [sh_c3] ──▶ 🏁 A Dojo That Takes No Apprentice
verina:        [vl_c1] ──▶ [vl_c2] ──▶ [vl_c3] ──▶ 🏁 The Pot That Never Wilted
baizhi:        [bz_c1] ──▶ [bz_c2] ──▶ [bz_c3] ──▶ 🏁 On the Back of a Prescription
```

- **Opening a chain.** Set `"unlock_chain": "<chain-id>"` on a character card
  (the chain becomes available once that character is met) or on an event's
  `"unlock_chain"` field to open it on the spot when that event resolves.
  Already-active chains are **always evaluated first**, so a chain you're mid-way
  through will never be interrupted by a fresh random encounter.
- **Advancing.** The chosen effect names its destination: put
  `"next_on": "<next-node-id>"` on that effect object. The lookup key is the
  effect's `"key"`; a key `"*"` acts as the catch-all for any option that
  didn't name a destination. Forgetting `next_on` simply stalls the chain on
  that node — it won't crash, and the graph will flag a dangling end.
- **Closing.** Reaching the last id in `nodes` fires the chain's `reward`
  (`aff` / `hp` / `sta` / `str` / `flags`), locks the character into the
  ending stage, and marks the chain `done` — **the same chain will never fire
  again**, even if you keep playing.
- **Shared / school-wide chains.** Leave `owner` unset and gate it with
  `req_flags` plus a day window; the festival chain ends in a whole-school
  coda.

See the full spec in [`IMPORT_FORMAT.md`](./IMPORT_FORMAT.md) (Chinese; field
names are identical to what's described here).

---

## File layout

```
WuwaSchool/
├── wuwa_school.py          # the whole game, scheduling only — no prose, no numbers
├── characters.json         # built-in 5: Jinhsi / Verina / Sanhua / Baizhi /秧秧
├── events.json             # daily encounters + school-wide public events
├── chains.json             # chain definitions (id / owner / node order / reward)
├── chain_events.json       # text + choices for every chain node
├── IMPORT_FORMAT.md        # format spec for content authors
├── mods/                   # ★ drop your json here, loaded automatically
│   ├── changli.json        #   example: a new character + her events
│   └── ...
├── graphs/                 # produced by the `graph` command
│   ├── event_chain.png     #   directed chain graph (needs graphviz)
│   └── event_chain.dot     #   DOT source, re-render however you like
├── wuwa_save.json          # save file (written by the game, don't hand-edit)
├── README.md               # this project's Chinese readme
└── README_EN.md
```

**Design rule:** the script contains **zero dialogue and zero balance numbers**.
Adding a character, retuning affinity or swapping an ending means editing JSON
only — no Python touch required.

---

## Modding (important)

### 1. How to import

Drop a `.json` into **`./mods/`**, next to `wuwa_school.py`, then either:

- **restart** the game — the scan prints something like
  `角色 6 · 事件 14 · 结局链 7`, plus one `[mods]` line per loaded file; or
- **stay in-game and type `reload`** — same scan, no restart needed.

New characters and events enter the random pool from the **next day** onward.

### 2. Does it overwrite the built-ins?

**Appending is the default; overwrite is opt-in and explicit.** Load order is
always *built-ins first, then `mods/` in filename-sorted order*.

| Situation | Result |
|---|---|
| mod uses a **brand-new id** (character / event / chain) | built-ins **and** mod content coexist and both roll. |
| mod reuses an **existing id** | the later load wins → **that single record is replaced** (great for rewriting a line or rebalancing a node). |
| two mods collide on the same id | filename sort decides it; **don't ship mods with overlapping ids**. |
| one file is malformed / missing a field / wrong type | exactly one warning line: `[mods] skipped xxx.json: …`. Everything else loads. **No save corruption, no crash.** |

So importing 长离 (Changli) will not bump Jinhsi out of the pool — the five
built-ins are the floor, they're always there.

### 3. One file, four buckets

The loader decides type from the `"type"` field, **not the filename**, and it
expects one record per file. To ship a character and her content together,
split them into one object per record — there is no magic `"characters": [...]`
array wrapper:

```json
[
  { "type": "character", "id": "Changli", "name": "Changli", "title": "Art teacher", "hp": 85, "base_aff": 10, "style": "gentle", "quote": "It's ruined.", "color": "#FF8A65" },
  { "type": "event", "id": "e_cl_01", "kind": "encounter", "owner": "Changli", "day_min": 3, "weight": 6, "text": "The art room light is still on. A profile sketch sits on the easel.", "effects": [ { "key": "a", "text": "Bring her coffee", "aff": 8, "hp": -2, "set_flags": ["cl_coffee"] }, { "key": "b", "text": "Pretend you're just passing by", "aff": 1 } ] },
  { "type": "chain", "id": "changli_main", "owner": "Changli", "name": "The Unsigned Painting", "nodes": ["cl_c1", "cl_c2", "cl_c3"], "reward": { "aff": 30, "hp": 10 } },
  { "type": "event", "id": "cl_c1", "kind": "chain", "owner": "Changli", "text": "It's ruined, she says, and flips the sheet over. Her ears are pink.", "effects": [ { "key": "a", "text": "It isn't.", "aff": 12, "next_on": "cl_c2" }, { "key": "b", "text": "Look away and say nothing.", "aff": 2, "next_on": "cl_c2" } ] }
]
```

> Four records, **one JSON array**, one `type` per element. This is the form
> the loader actually accepts: `json.load` on the whole file, then each object
> is routed by its `type`. A bare concatenation of objects or a missing comma
> is rejected as `Extra data`. Prefer one record per file? Name them however
> you like — the loader scans every `*.json` in `mods/` and ignores the name.

> Each line is **one independent JSON object** — `type` is required on every
> line, there is no wrapping array and no comma between records. The loader
> calls `json.loads` per line, so a pretty-printed multi-line object or a
> stray comma is rejected as `Extra data`. Prefer readable formatting? Put each
> record in its own `.json` file instead.

> ⚠️ **Breaking with the Chinese README:** an earlier draft claimed you could
> wrap everything in one object under `"characters" / "events" / "chains" /
> "chain_events"`. **That wrapper is not supported by the loader** — the file
> would be rejected as "root must be object or array" (objects without a
> `type` are treated as events, and an array needs every element to carry its
> own `type`). Use the per-record form above; it's what the code actually
> accepts.

### 4. Sharp corners

- `reload` is **additive + replace**, never a reset of today's already-fired
  events. Edited a **built-in** json and want it reflected? Restart.
- Every chain node needs a `next_on` (or it just stalls on that node). The
  final node has no destination — the chain's `nodes` order is what actually
  triggers the reward and ending.
- A character who exists in your save but has vanished from the current pool
  (you removed the mod) becomes an **orphan**: affinity and flags are preserved
  in the save and displayed normally, she simply stops rolling events. Drop the
  mod back in and progression resumes.
- `chain_events.json` node ids are validated at scan time; a missing target is
  reported as a warning and that chain simply won't reach its ending.

---

## Saving & loading

- `save` → `wuwa_save.json` in the same directory.
- `2` at the title screen loads it: day / weekday / term, all three stats,
  every character's affinity and stage, every flag, active and cleared chains,
  chain progress, and the RNG seed (so your run stays deterministic).
- Loading against a fresh pool **adds** new characters automatically and keeps
  missing ones as orphans instead of erroring.
- Multiple runs: copy `wuwa_save.json` aside and start a new game.

---

## Chain visualiser

Type `graph` (or `g`) in-game:

```text
        [Jinhsi] The Tide Remembers You
  jx_c1 ──▶ jx_c2 ──▶ jx_c3 ──▶ 🏁 reward: +30 aff

        [Sanhua] A Dojo That Takes No Apprentice
  sh_c1 ──▶ sh_c2 ──▶ sh_c3 ──▶ 🏁 reward: +30 aff
  ⚑ you've cleared this chain (it will not trigger again)
```

- **With Graphviz:** `graphs/event_chain.png` — boxed nodes, arrows, `⚑` for
  cleared, `🔒` for unlocked-but-untouched.
- **Without Graphviz:** text chart to the terminal, and the `.dot` is still
  written, so locally you can
  `dot -Tpng graphs/event_chain.dot -o graphs/event_chain.png` any time.

---

## Writing your own content: minimal template

Save the snippet below as `mods/my_char.json` and it runs:

```json
{ "type": "character", "id": "Changli", "name": "Changli", "title": "Art teacher", "hp": 85, "base_aff": 10, "style": "gentle", "quote": "It's ruined.", "color": "#FF8A65" }
{ "type": "event", "id": "e_cl_01", "kind": "encounter", "owner": "Changli", "day_min": 3, "weight": 6, "text": "The art room light is still on. A profile sketch sits on the easel.", "effects": [ { "key": "a", "text": "Bring her coffee", "aff": 8, "hp": -2, "set_flags": ["cl_coffee"] }, { "key": "b", "text": "Pretend you're just passing by", "aff": 1 } ] }
{ "type": "chain", "id": "changli_main", "owner": "Changli", "name": "The Unsigned Painting", "nodes": ["cl_c1", "cl_c2", "cl_c3"], "reward": { "aff": 30, "hp": 10 } }
{ "type": "event", "id": "cl_c1", "kind": "chain", "owner": "Changli", "text": "It's ruined, she says, and flips the sheet over. Her ears are pink.", "effects": [ { "key": "a", "text": "It isn't.", "aff": 12, "next_on": "cl_c2" }, { "key": "b", "text": "Look away and say nothing.", "aff": 2, "next_on": "cl_c2" } ] }
```

> Each line is **one independent JSON object** — `type` is required on every
> line, there is no wrapping array and no comma between records. The loader
> calls `json.loads` per line, so a pretty-printed multi-line object or a
> stray comma is rejected as `Extra data`. Prefer readable formatting? Put each
> record in its own `.json` file instead.

For every recognised field, accepted values and the gating rules
(`req_flags` / `block_flags` / `day_min` / `day_max` / `cost` / `weight` /
`once` / `hidden` / `next_on`), see
[`IMPORT_FORMAT.md`](./IMPORT_FORMAT.md).

---

## Reference: field glossary

### Character

| Field | Type | Default | Notes |
|---|---|---|---|
| `type` | string | — | **`"character"`** (also `char` / `角色`) |
| `id` | string | — | **required**, unique. Collision = replacement. |
| `name` | string | = `id` | Display name. |
| `title` | string | `""` | Shown in the affinity panel. |
| `hp` | int | 80 | Starting HP, 0–100. |
| `base_aff` | int | 0 | Starting affinity. |
| `color` | string | `"#888888"` | ANSI/hex colour used for the name in the terminal. |
| `style` | string | `""` | Flavour tag (not balancing). |
| `quote` | string | `""` | Idle flavour line. |
| `unlock_chain` | string | — | Chain id auto-opened once this character is met. |

### Event / chain node (both are `type: "event"`)

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | string | — | **required**, unique, used for `once` and `next_on` lookups. |
| `kind` | string | `"encounter"` | `encounter` · `public` · `weekend` · `chain`. `chain` without an `owner` is rejected as unavailable. |
| `owner` | string | none | Character id; omit for a school-wide public event. |
| `day_min` / `day_max` | int | `1` / `9999` | Day window. |
| `weight` | float | `1.0` | Relative draw weight (daily encounter pool). |
| `once` | bool | `false` | If true, fires at most once per run (tracked in `used_once`). |
| `hidden` | bool | `false` | Never offered by the scheduler; still reachable via `next_on`. |
| `req_flags` | string[] | `[]` | All must be present in the global flag set. |
| `block_flags` | string[] | `[]` | None may be present. |
| `cost` | object | `{}` | `{ "hp": n, "stam": n, "str": n }` paid **before** effects. Option is hidden when unaffordable. |
| `text` | string | `""` | Event body; `\n` is honoured. |
| `effects` | array | `[]` | See below. |
| `next_on` | string | — | Legacy shorthand on the event. **Preferred:** put `"next_on": "<node-id>"` directly on the chosen effect object (keyed by `key`) — see the template below. `"*"` means "any option not otherwise mapped". |
| `set_flags` | string[] | `[]` | Flags written to the global set after resolution. |
| `unlock_chain` | string | — | Chain id opened on resolution. |

### Effect object (one entry per choice)

| Field | Type | Meaning |
|---|---|---|
| `key` | string | Choice id, referenced by `next_on`. |
| `text` | string | The line the player actually picks. Put the cost in the label — players appreciate it. |
| `target` | string | `"@self"` = player stats · `"@all"` = every character · else a character `id` (default: the event's `owner`). |
| `aff` | int | Affinity delta for the target; may be negative. |
| `hp` / `sta` / `str` | int | Stat delta, clamped to 0–100. |
| `reason` | string | Flavour suffix in the log line. |
| `set_flags` | string[] | Flags set when this choice wins. |
| `next_on` | string / object | Shorthand: a plain string is treated as the next node id. |

> All deltas are `clamp(0, 100)`. STA is additionally bounded by the day's
> `STA max`. Negative `hp` gain on a weekend plan's `gain` block is how the
> dojo "costs" HP — yes, the field name is counter-intuitive; it's a straight
> add.

### Chain (`type: "chain"`)

| Field | Type | Notes |
|---|---|---|
| `id` | string | **required** |
| `owner` | string | Character id, or omit for a shared school-wide chain. |
| `name` | string | Ending title, shown in the graph. |
| `description` | string | Flavour, shown in `status`. |
| `color` | string | Hex for the graph node. Default `#C77DFF`. |
| `nodes` | string[] | **required** — ordered event ids. The last one triggers `reward`. |
| `reward` | object | `{ "aff": n, "hp": n, "stam": n, "str": n, "flags": [...] }` applied on closure. |

### Tuning cheatsheet

| Magnitude | Feel |
|---|---|
| `aff` ±3–5 | Idle chitchat. |
| `aff` ±6–9 | A real attitude shift. |
| `aff` ±10–12 | Plot beat / confession tier. |
| `stam` −8…−12 | Late night, sport, moving furniture — you'll feel it tomorrow. |
| `hp` −3…−4 | Pushed through the day; your STA ceiling drops next morning. |
| `str` −4…−5 | Genuinely soothed; `+3` and up is a fresh headache. |

---

## FAQ

**Q: I hit Enter and nothing story-like happened.**
A: Every event is weighted and gated. Low weight or a day-window you haven't
reached yet means a perfectly ordinary, uneventful day. Bump `weight`, or use
`status` to confirm the character is met and the day is in range.

**Q: Why no encounters on weekends?**
A: By design — Sat/Sun show the getaway board instead, and the daily
encounter pool is paused.

**Q: My new character doesn't show up after `status`.**
A: Check the file is inside `mods/`, ends in `.json`, and has
`"type": "character"` plus a unique `id`. Then `reload`. If the startup log
says `[mods] skipped …`, fix the field it names — the game keeps running.

**Q: Can I retune the stamina curve or the affinity cap?**
A: The curve is three lines in `stam_max()` / `new_day()` (constants, edit
once, global effect). The cleaner move is to express costs and rewards in your
event/plan json and leave the formula alone.

**Q: My terminal shows boxes instead of emoji.**
A: The script is UTF-8. On Windows `cmd`, switch the console to UTF-8
(`chcp 65001`) or use Windows Terminal / PowerShell.

**Q: Is the Chinese README's mod skeleton wrong?**
A: The *old* Chinese README showed a single object with `"characters": [...]`
etc. That form is **not** accepted by the loader. This English readme's
per-record form (one `{...}` per line, each with its own `type`) is the
canonical one — and the Chinese README should be updated to match.

---

*Fan work. Characters belong to their respective rights holders. This project is
for learning and tinkering — edit it, fork it, ship your own mods, no
permission needed.*
