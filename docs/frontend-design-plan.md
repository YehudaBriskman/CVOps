# CVOps — Frontend & Web Design Plan

> Design plan for two surfaces:
> 1. **The App** (`services/frontend`) — the ML-lifecycle dashboard. Dark-first, dense, precise. Centerpiece is a React-Flow workflow DAG editor.
> 2. **The Website** (`services/website`, new) — marketing: landing (with 3D), docs, blog, contact.
>
> Target quality bar: Linear / Vercel / Resend / Railway. Stack: React 18 + Vite + Tailwind + `@xyflow/react`.

---

## 0. TL;DR — what we're building

| | The App (dashboard) | The Website (marketing) |
|---|---|---|
| **Feel** | A precision instrument. Quiet, dense, fast. Dark by default. | Cinematic and confident. A 3D "data DAG" hero, then calm docs. |
| **Where** | `services/frontend` (exists, ~85% scaffolded) | `services/website` (new package — Next.js) |
| **Hero feature** | Workflow canvas (react-flow) that doubles as a *live run map* | WebGL hero where a point-cloud morphs into a pipeline graph |
| **Color** | Near-black surfaces + **iris violet** (brand) + **lime signal** (live data) | Same tokens, more saturated, more space |
| **Type** | Geist Sans (UI) + Geist Mono (hashes, refs, code) | Geist Sans + a display cut for the hero |

The single most important idea: **the workflow canvas is not just an editor — it's the same surface you watch a run execute on.** Build → Run → Debug all happen on one map. That is the product's signature.

---

## 1. Design principles (the "why" behind every choice)

1. **Show the lineage, always.** This product's whole reason to exist is reproducibility: a model knows its commit, a commit knows its samples, a run knows its config hash. The UI must make those links *one click away* everywhere. Every model card links to its training commit; every commit links to its run; every run links to its workflow version.
2. **Dense, but never cramped.** Developer tools earn trust by showing a lot without clutter. We use an 8px rhythm, tabular numbers, and monospace for any identifier so columns line up and nothing jumps.
3. **Dark-first, not dark-only.** The default theme is dark (this is where developers live). Light is a first-class second theme via semantic tokens — never hardcoded hex in components.
4. **Motion = cause and effect.** Animation only ever explains a state change (a step starts running, a gate opens, a commit lands). No decorative motion in the app. Respect `prefers-reduced-motion`.
5. **The empty state is a feature.** Every list/canvas/graph has a designed empty state that teaches the next action — not a blank panel.
6. **Speed is the aesthetic.** Optimistic updates, skeletons over spinners, virtualized lists, presigned URLs straight to storage (never proxy image bytes). Perceived latency is part of the design.

---

## 2. Design tokens (the foundation — build this first)

Everything below becomes CSS variables + a Tailwind theme extension. **No component ever uses a raw hex.** This is the source of truth.

### 2.1 Color — surfaces (dark theme)

A cool near-black base. Surfaces get *lighter* as they get closer to the user (elevation = lightness), which reads more naturally on dark than shadows do.

| Token | Hex | Use |
|---|---|---|
| `bg-sunken` | `#07080A` | App background behind everything, canvas backdrop |
| `bg-base` | `#0A0B0D` | Default page background |
| `surface-1` | `#111317` | Cards, sidebar, panels |
| `surface-2` | `#16181D` | Raised: popovers, dropdowns, node bodies |
| `surface-3` | `#1C1F26` | Highest: modals, hovered rows |
| `border-subtle` | `#23262E` | Hairlines between rows |
| `border-default` | `#2D313B` | Card/input borders |
| `border-strong` | `#3A3F4B` | Focus-adjacent, dividers that must read |

### 2.2 Color — text

| Token | Hex | Use |
|---|---|---|
| `text-primary` | `#F4F6F9` | Headings, primary content |
| `text-secondary` | `#A2A9B6` | Body, labels |
| `text-tertiary` | `#6B7280` | Metadata, timestamps, placeholders |
| `text-disabled` | `#4A4F5A` | Disabled |

Body text on `surface-1` clears 4.5:1. Tertiary is reserved for non-essential metadata only (it sits ~3:1 — never use it for anything a user must read to act).

### 2.3 Color — brand & signal (the signature duotone)

The memorable move. Two accents with **distinct jobs** so they never fight:

- **Iris** = the platform. Buttons, links, focus rings, active nav, selection. Calm, premium.
- **Lime signal** = *your data, alive*. Live run edges, the "running" pulse, streaming indicators, "now" markers. Energy.

| Token | Hex | Use |
|---|---|---|
| `iris-500` | `#7B6CF6` | Primary brand / buttons / links |
| `iris-400` | `#8E80FF` | Hover |
| `iris-600` | `#5D4FE0` | Active/pressed |
| `iris-glow` | `rgba(123,108,246,.35)` | Focus ring, glow |
| `signal-500` | `#C6F24E` | Live/active data flow, running edges |
| `signal-600` | `#B4E62B` | Live text on dark |
| `signal-glow` | `rgba(198,242,78,.30)` | Pulse halo |

> Rule: lime never appears as a static decoration. If it's lime, something is *live*. That discipline is what makes it feel expensive instead of neon.

### 2.4 Color — semantic / run status

Run statuses are core domain objects (`pending | running | waiting | succeeded | failed | canceled`). Each gets a fixed color + icon + label (never color alone — colorblind-safe):

| Status | Token | Hex | Icon | Note |
|---|---|---|---|---|
| pending | `status-pending` | `#6B7280` slate | dashed circle | not started |
| running | `status-running` | `#C6F24E` lime | spinner/pulse | uses the live signal |
| waiting | `status-waiting` | `#FBBF24` amber | pause/gate | human gate open |
| succeeded | `status-success` | `#34D399` emerald | check | terminal |
| failed | `status-failed` | `#FB7185` rose | x/alert | terminal, has `error` |
| canceled | `status-canceled` | `#71717A` zinc | slash | terminal |
| info | `status-info` | `#38BDF8` sky | info | events, neutral notices |

### 2.5 Typography

| Role | Font | Notes |
|---|---|---|
| UI / body | **Geist Sans** (fallback Inter) | proven for dense dashboards; enable `tabular-nums` for all data |
| Code / data | **Geist Mono** (fallback JetBrains Mono) | every hash, ref, ID, `$steps.x.outputs.y`, metric, log line |
| Display (marketing only) | Geist Sans tight, or **Clash Display** for the hero | expressive cut, marketing pages only |

Type scale (rem): `12 / 13 / 14 / 16 / 18 / 20 / 24 / 30 / 38 / 48`. Body 14px in app (dense), 16px on web. Line-height 1.5 body, 1.2 headings. Mono identifiers get a faint `surface-2` chip background + `border-subtle`.

### 2.6 Space, radius, shadow, motion

- **Spacing:** 4px base, 8px rhythm: `4 8 12 16 24 32 48 64`.
- **Radius:** `sm 6px` (inputs, chips) · `md 10px` (cards, nodes) · `lg 14px` (modals) · `full` (pills, avatars).
- **Shadow (dark uses light, not shadow):** elevation = surface lightness + a 1px `border` + an optional inner top highlight `inset 0 1px 0 rgba(255,255,255,.04)`. Reserve real drop-shadows for floating layers (popover/modal): `0 8px 30px rgba(0,0,0,.5)`.
- **Motion:** durations `120ms` (micro), `200ms` (default), `320ms` (enter), exits ~70% of enter. Easing: `cubic-bezier(.2,.8,.2,1)` (ease-out) for enter, ease-in for exit. Springs for canvas drag. One global token set — everything shares the rhythm.
- **Z-index scale:** `base 0 · sticky 10 · dropdown 20 · canvas-panel 30 · modal 40 · toast 50 · tooltip 60`.

---

## 3. The App — information architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Top bar: Org switcher · Project switcher · ⌘K · run feed · me │
├──────────┬───────────────────────────────────────────────────┤
│ Sidebar  │                                                     │
│  Overview│   Main content (route)                              │
│  Data ▸  │                                                     │
│   Sources│                                                     │
│   Samples│                                                     │
│   Ontolog│                                                     │
│  Datasets│                                                     │
│  Workflws│                                                     │
│  Runs    │                                                     │
│  Models  │                                                     │
│  Settings│                                                     │
└──────────┴───────────────────────────────────────────────────┘
```

- **Two-level context:** Org (tenant) → Project. Both switchable from the top bar. Everything below is project-scoped (matches the API's `org_id` + `project_id` filtering).
- **Sidebar = primary nav**, collapsible to icons, persists state (Zustand). Active route highlighted with an iris left-bar + filled icon.
- **⌘K command palette** is the power-user spine: jump to any project/dataset/workflow/run, run actions ("New run", "Create commit"), search samples by id. This is the Linear-grade touch.
- **Global run feed** (top-bar popover): a live list of in-flight runs with status dots, fed by SSE. Click → run view. A run going `waiting` (gate) raises an amber badge — that's the "you're needed" signal.
- **Breadcrumbs** on deep pages (Dataset ▸ commit `a1b2c3` ▸ diff). Every screen deep-linkable by URL.

### Route map (already scaffolded in `App.tsx`)

| Route | Page | Core API |
|---|---|---|
| `/login`, `/register` | Auth | `/auth/*` |
| `/projects` | Project grid | `GET /projects` |
| `/projects/:id` | Project overview / activity | events, runs, datasets |
| `/projects/:id/data-sources` | Data sources + upload | `/data-sources`, presigned PUT |
| `/projects/:id/samples` | Sample browser | `GET /projects/:id/samples` (cursor) |
| `/projects/:id/ontologies` | Ontology editor | `/ontologies`, `/label-classes` |
| `/projects/:id/datasets` | Datasets list | `GET /projects/:id/datasets` |
| `/datasets/:id` | Commit graph + branches | `/datasets/:id/commits`, `/refs` |
| `/datasets/:id/commits/:cid` | Commit detail / diff | `/commits/:cid`, `/diff` |
| `/projects/:id/workflows` | Workflow list | `GET /projects/:id/workflows` |
| `/workflows/:id` | **Workflow canvas (builder)** | `/workflows/:id`, `/registry/types` |
| `/runs/:id` | **Run view (live)** | `/runs/:id`, SSE `/events/stream`, gates |
| `/projects/:id/models` | Model registry | `GET /projects/:id/models` |
| `/models/:id` | Model detail / compare | `/models/:id`, `/weights-url` |
| `/projects/:id/settings` | Project + members | `/projects/:id`, `/orgs/current/members` |

---

## 4. The Workflow Canvas — the centerpiece (react-flow)

This gets the most thought. It has **three modes on one canvas**: **Build**, **Run** (live), and **Diff** (compare versions). Same nodes, same layout — only the overlay changes. That continuity is the whole idea.

### 4.1 Node anatomy

Each node = one step in the workflow `definition.steps[]`. Designed as a compact "instrument card":

```
┌─────────────────────────────────┐
│ ◧ EXTRACT FRAMES        ⋯       │  ← category icon + type label + menu
│ extract                          │  ← step.id (mono, tertiary)
├─────────────────────────────────┤
│ fps 2 · max_frames 500           │  ← config summary (key params, mono)
├─────────────────────────────────┤
○ images          annotations ●    │  ← typed ports (left=in, right=out)
└─────────────────────────────────┘
   status strip (left edge): ▍running
```

- **Category color** on the left accent + icon (extract / label / review-gate / commit / export / train). Gate steps (`is_gate`) get a distinct amber-ringed icon so they're recognizable at a glance.
- **Typed handles (ports):** inputs on the left, outputs on the right, each labeled with its name from the step schema (`images`, `annotations`, `commit`…). Hovering a port shows its type. This is how `$steps.<id>.outputs.<name>` references are drawn — you literally connect output port → input port and the ref string is generated for you.
- **Config summary line** shows the 2–3 most important config values inline (from `ui_hints` ordering) so you don't have to open each node to read the pipeline.
- **Status strip** (left edge, 3px): in Run mode it animates per status.

### 4.2 Edges

- Default: smooth bezier, `border-strong`, 1.5px. Connected to typed ports.
- **Type-mismatch** (output type ≠ input type): edge turns rose, dashed, with a small ⚠ — instant validation feedback while wiring.
- **Run mode — live:** an edge whose upstream step is `running` animates a **lime signal** flowing along it (animated dash / moving gradient). When data has "passed" an edge (upstream succeeded), it goes solid emerald. This is the "watch your data move" moment.

### 4.3 Build mode interactions

- **Add steps:** a left **Step Palette** (grouped by registry `category`, fetched from `GET /registry/types?category=step`) — drag onto canvas, *or* ⌘K → "Add step" → fuzzy pick. Palette items show icon + name + one-line description from the schema.
- **Config panel (right):** clicking a node opens a slide-in panel with an **auto-generated form** from the step's JSON Schema via `@rjsf` (already installed), honoring `ui_hints` for widget/order/grouping. This is why the registry exists — zero hand-written forms per step type. Validation errors (ajv) show inline under each field.
- **Wiring refs:** drag output→input to create edges; the input's ref (`$steps.extract.outputs.images`) is written automatically. Inputs can also bind to `$run.params.*` via a dropdown in the config panel for run-time parameters.
- **Validation (live, before save):** cycle detection (must stay a DAG — the engine runs Kahn's topo sort), unresolved required inputs, missing required config, unknown step types. A bottom status bar shows "✓ valid DAG · 6 steps" or "2 issues" with a click-to-jump list.
- **Auto-layout:** a "Tidy" button runs **ELK** (`elkjs`) or **dagre** layered layout left→right. Manual positions are preserved per node otherwise (store `x,y` in a UI-only layer; the API `definition` stays `{steps, edges}` — keep layout in a sibling `ui` blob or local cache so we don't pollute the engine contract).
- **Power moves:** multi-select (marquee), copy/paste steps, undo/redo (Zustand + a history middleware), keyboard nudge, `⌫` to delete, minimap, zoom controls, dotted grid with snapping.
- **Save:** `PATCH /workflows/:id` (bumps version). Show a subtle "v3 → v4" toast. Unsaved-changes guard on navigate.

### 4.4 Run mode (same canvas, live)

When you trigger a run (`POST /workflows/:id/runs`) you can stay on the canvas in **Run mode** (or open `/runs/:id` which shares the component):

- Each node shows its **step run status**, driven by the SSE `/runs/:id/events/stream`. Nodes transition pending → running (lime pulse) → succeeded (emerald) / failed (rose) / waiting (amber).
- **Gate nodes pulse amber** when the run is `waiting` on them, with an inline "Resolve" button → opens the gate resolution drawer (accept/reject + notes → `POST /runs/:id/gates/:step_id/resolve`).
- **Failed node** shows the `error` inline + a "view logs" link (logs from `logs_blob_hash` via presigned GET).
- Clicking any node opens the **step run detail**: resolved `input_refs`, `output_refs`, `config`, `metrics`, timing, attempt count. This is the debug surface.
- **Idempotency reuse** is visualized: steps whose outputs were reused from a prior identical run (same `sha256(type+config+inputs)`) get a subtle "cached ↺" badge instead of re-running — so users understand why a run finished in 2s.

### 4.5 Diff mode

Compare two workflow versions (or the workflow-as-saved vs the version a past run used). Nodes/edges added = emerald outline, removed = rose dashed ghost, changed config = amber dot. Helps answer "what changed since the run that worked?".

### 4.6 Libraries to add for the canvas

- `@xyflow/react` (installed) · `elkjs` or `dagre` (auto-layout) · `zustand` (canvas store, installed) · `@rjsf/core` + `validator-ajv8` (config forms, installed) · `nanoid` (step ids) · a small custom history middleware for undo/redo.

---

## 5. The App — page-by-page direction

### 5.1 Project Overview (`/projects/:id`)
A calm dashboard, not a chart dump. Three bands:
1. **Pulse** — small stat tiles: active runs, datasets, samples, latest model metric (tabular mono numbers, no heavy chart chrome).
2. **Activity timeline** — the `Event` stream rendered as a vertical timeline (commits landed, runs finished, gates resolved), each with actor + relative time. This is the lineage made visible.
3. **Quick actions** — "New run", "New workflow", "Upload data" as the primary CTAs (one primary iris button, rest secondary).

### 5.2 Data Sources (`/projects/:id/data-sources`)
- Table of sources with `type` (video/image_folder/external_uri), `status` chip, metadata (fps, duration, codec).
- **Upload flow:** register → receive `presigned_put_url` → upload bytes **directly to storage** (progress bar, never through the API) → `POST /data-sources/:id/confirm-upload` → status moves to processing, which kicks off a frame-extraction run. Show that run inline.
- Empty state teaches: "Drop a video to extract frames."

### 5.3 Sample Browser (`/projects/:id/samples`)
The heaviest data surface — make it *fast*.
- **Virtualized masonry grid** (react-virtuoso or react-window). Thumbnails loaded from `GET /samples/:id/image-url` (presigned, direct from storage), `loading="lazy"`, fixed aspect ratio boxes to kill layout shift.
- **Cursor pagination** (the project's standard `{items, next_cursor}`) → infinite scroll.
- **Filter rail:** by source, by class, by `review_status` (unreviewed/accepted/rejected) — color-coded.
- **Sample detail (lightbox):** the image with **annotation overlays** rendered on a canvas layer — bounding boxes / polygons from the latest `AnnotationRevision.payload`, colored by `LabelClass.color`. A revision history strip lets you scrub provenance (model vs human vs import) — append-only, so it's a clean timeline.

### 5.4 Datasets + Commit Graph (`/datasets/:id`)
The git-for-data surface — lean into the git metaphor hard.
- **Commit graph:** a vertical git-style DAG (commits, `parent_commit_id`, `second_parent_commit_id` for merges), branch/tag refs (`Ref`) as colored labels on the right. Branches = mutable (movable head icon), tags = immutable (lock icon). Render with a lightweight custom SVG graph or reuse react-flow in a constrained vertical layout.
- Each commit row: message, author, relative time, and a stats sparkline (`stats.class_counts`, `stats.splits` train/val/test).
- **Commit detail / diff (`/commits/:cid`):** `added / removed / changed` samples between commits via `GET /datasets/:id/diff?from=&to=`, with class-count deltas. "Tag this commit `v1.0`" action → `POST /datasets/:id/refs`.

### 5.5 Run View (`/runs/:id`)
Two layouts, toggle: **Graph** (the canvas in Run mode, §4.4) and **Timeline** (linear).
- **Timeline:** step run cards in topo order, each a colored status row that expands to inputs/outputs/config/metrics/logs. Live via SSE.
- **Gate banner:** when `waiting`, a prominent amber banner at top — "Human review required: 42 jobs in CVAT" — with Accept / Reject + notes. Resolving resumes the run.
- **Logs:** monospace viewer, virtualized, with a download (presigned). Auto-scroll with a "jump to live" pill.

### 5.6 Model Registry (`/projects/:id/models`, `/models/:id`)
- Cards: base model, key metric (mAP etc., big tabular number), `trained_on_commit_id` chip (click → that exact commit), hyperparams.
- **Compare view:** select 2+ models → side-by-side metrics table + a small grouped bar/line chart (respect chart a11y: legend, tooltips, not color-only). The reproducibility story lives here: each column shows seed, `code_version`, `env_hash`, commit.
- "Download weights" → `GET /models/:id/weights-url` (presigned).

### 5.7 Auth, Ontologies, Settings
- **Auth:** centered card on a subtly animated dark gradient (a faint moving DAG pattern in the bg). Email/password, inline validation on blur, password show/hide, clear error recovery. Token storage + axios refresh interceptor (rotate refresh tokens, blacklist on logout).
- **Ontology editor:** list of `LabelClass` rows — stable `class_key` (mono), display name, a color swatch picker, drag-to-reorder (`sort_order`). Live preview of how boxes will look.
- **Settings:** project fields + **members table** (invite by email, role dropdown, remove) from `/orgs/current/members`. Destructive actions (delete project) isolated at the bottom in a "danger zone" with confirm.

### 5.8 Cross-cutting UI system
- **States for every async surface:** skeleton (loading >300ms), empty (teaches next action), error (cause + retry), success (toast, aria-live). No raw spinners on full pages.
- **Toasts:** bottom-right, auto-dismiss 4s, `aria-live="polite"`, never steal focus. Undo affordance for destructive/bulk.
- **Tables:** sticky header, sortable (`aria-sort`), tabular-nums, row hover = `surface-3`, zebra off (borders instead).
- **Accessibility baseline:** 4.5:1 text contrast, visible 2px iris focus rings (never removed), full keyboard nav, focus moves to main on route change, icon buttons get `aria-label`, status never by color alone.

---

## 6. The Website (marketing) — `services/website`

A **separate Next.js (App Router) package** — better for SEO, static docs, blog, and an MDX content pipeline than the Vite SPA. Shares the same design tokens (publish them as a tiny `packages/design-tokens` so app + site never drift). 3D via **React Three Fiber** (`@react-three/fiber` + `drei` + `postprocessing`).

### 6.1 Landing page (section by section)

1. **Hero — the 3D moment.** A WebGL canvas: a drifting **point cloud** (evokes image samples / CV) that, as you scroll or on load, **morphs into a clean pipeline DAG** — nodes and lime edges snapping into place. Headline over it: *"Version your data. Orchestrate your pipelines. Ship reproducible models."* One iris CTA ("Start free"), one ghost ("Read the docs"). Respect `prefers-reduced-motion` → swap to a static rendered still. Keep it 60fps: instanced points, low draw calls, pause when offscreen.
2. **Logo / social proof strip** — muted, monochrome logos.
3. **The problem** — three columns: scattered data versions, brittle pipelines, irreproducible models. Calm, text-led.
4. **Feature showcase (scrollytelling)** — as you scroll, a pinned product frame swaps: commit graph → workflow canvas → live run → model compare. Each with a one-line claim. Real UI screenshots/recreations, bordered with the app's surface tokens.
5. **The workflow canvas, interactive** — an embedded *live* mini react-flow the visitor can actually drag. Nothing sells the centerpiece like touching it.
6. **Reproducibility section** — a visual lineage chain (model → commit → samples → run) animating its links lighting up. The product's soul.
7. **Code / API peek** — a mono code block (the workflow `definition` JSON, or a curl) with a copy button. Speaks to developers.
8. **Pricing** (if relevant) — clean tiers, one highlighted.
9. **Final CTA** + footer (docs, blog, GitHub, contact, status).

Motion language for the site: generous but purposeful — staggered reveals (30–50ms), parallax kept subtle, spring-based. One or two focal animations per viewport, never a carnival.

### 6.2 Docs
- **Three-pane layout** (Nextra/Mintlify-style): left nav tree, center MDX content (max ~72ch measure), right "on this page" TOC.
- Instant client-side search (⌘K), code blocks with copy + language tabs, callout components (note/warning/tip), dark-first with a light toggle. Versioned if needed.
- Auto-generate the **API reference** from the FastAPI OpenAPI schema (the app already exposes it) — keeps docs honest.

### 6.3 Blog
- Index: a featured post (large card with cover) + a clean grid. Tags, author, read time.
- Post: centered ~68ch measure, big readable type, mono code blocks, generous vertical rhythm, prev/next, share. MDX so posts can embed live components (e.g. an interactive DAG).

### 6.4 Contact
- Two-column: a short form (name, email, message — inline validation, clear success state) + alternative channels (email, GitHub, community). Optional Cal.com embed for demos. A subtle 3D/gradient accent, not a full hero.

### 6.5 Website stack
`next` (App Router) · `@react-three/fiber` + `@react-three/drei` + `@react-three/postprocessing` · `framer-motion` (scroll/reveal) · `next-mdx-remote` or Contentlayer (blog/docs) · `tailwind` (shared tokens) · `lenis` (smooth scroll, optional, reduced-motion aware).

---

## 7. Shared frontend foundations (do these first)

These unblock everything and currently are stubs/empty in `services/frontend`:

1. **Design tokens → Tailwind theme** (`tailwind.config` extend + CSS vars for light/dark). Ship as `packages/design-tokens` so the website reuses them.
2. **Axios client + auth** (`lib/client.ts`): bearer interceptor, 401 → refresh-token rotation, logout blacklist. Token store in Zustand + localStorage.
3. **TanStack Query layer**: implement the 9 stub `api/*.ts` modules as typed hooks (`useProjects`, `useWorkflow`, `useRun`, `useSamples`…), with query-key conventions and `invalidate` on mutations. **No `any`** — Zod-validate responses at the boundary (matches the global rule).
4. **SSE hook** (`useRunStream`) for live runs + the global run feed.
5. **Component primitives** (the design system in code): Button, Input, Select, Dialog, Drawer, Toast, Tooltip, Tabs, Table, Card, Badge/StatusPill, Skeleton, EmptyState, CommandPalette. Build on **Radix UI** primitives (a11y for free) styled with Tailwind + tokens. (Add `@radix-ui/react-*`, `cmdk`, `sonner` or a custom toaster.)
6. **App shell**: Sidebar + Topbar + breadcrumbs + ⌘K wired to real navigation.

---

## 8. Suggested build order (phased)

**Phase A — Foundations (unblocks all):** tokens/Tailwind, primitives, auth + client + query layer, app shell. → Login works, projects list real data.

**Phase B — Core loop:** Data sources + upload, Sample browser (virtualized + presigned), Registry-driven config forms.

**Phase C — The centerpiece:** Workflow canvas Build mode (palette, nodes, typed ports, rjsf config, validation, save, auto-layout).

**Phase D — Live:** Run view + SSE + Run mode overlay on the canvas + gate resolution + logs.

**Phase E — Versioning:** Datasets commit graph, commit diff, refs/tags, ontology editor.

**Phase F — Models:** Registry + compare + reproducibility links.

**Phase G — Website:** new Next.js package — landing + 3D hero, docs (from OpenAPI), blog, contact.

Each phase is shippable on its own and respects the Controller→Service→Repository / no-`any` / cursor-pagination / presigned-URL conventions already in the codebase.

---

## 9. New dependencies summary

**App:** `@radix-ui/react-*`, `cmdk`, `sonner`, `react-virtuoso` (or `react-window`), `elkjs` (or `dagre`), `nanoid`, `zod`, `framer-motion` (light use), `@tanstack/react-query` (installed), `@rjsf/core` + `validator-ajv8` (installed), `@xyflow/react` (installed).

**Website (new `services/website`):** `next`, `@react-three/fiber`, `@react-three/drei`, `@react-three/postprocessing`, `framer-motion`, `lenis`, an MDX pipeline (`next-mdx-remote`/Contentlayer), shared `packages/design-tokens`.

---

*This is a design plan, not code. The two surfaces share one token system and one brand (iris + lime signal), but diverge in density: the app is a quiet precision instrument; the website is cinematic. The thread tying both together — and the thing to nail above all else — is the workflow canvas that you build on, run on, and debug on, all in one place.*
