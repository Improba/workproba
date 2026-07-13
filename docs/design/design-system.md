# Workproba Design System

Convergence document, synthesis of the debate between **Inès** (lead designer) and **Léa** (UX strategist). See `lea-ux.md` for the detailed UX proposal and flows.

This document is the source of truth for UI implementation.

## 0. Trade-off decisions (convergence)

| # | Trade-off | Decision | Reason |
|---|---|---|---|
| 1 | Single two-level sidebar vs two panels | **Single sidebar** (transient workspace switcher + dedicated conversations list) | Fewer surfaces to scan for a non-coder; stable anchor = active workspace at the top |
| 2 | Tree session badge (green "new" / orange "modified") | **Simplified to a single signal**: a cyan dot "touched during session", tooltip gives detail (created/modified) | Reduces visual load; detail remains accessible on hover |
| 3 | `Cmd/Ctrl+K` command palette | **Future release** (not at first launch) | Keep first launch sober; we'll add it as a discovery aid |
| 4 | Tree row height | **26 px** | Density/breathing room compromise for non-coders |
| 5 | Left sidebar hideable | **No** (collapsible to 56px icon rail, never fully hidden) | It's the stable anchor (Léa) |
| 6 | Right files panel | **Collapsible** (`Cmd/Ctrl+B`), state remembered per workspace | Small 13" screens |

## 1. Palette (Anubis tokens)

Improba identity serves as **accent and branding**, not chat background. Chat reads in sober light mode. Teal blue `#203D52` = branding + active states; cyan `#3ECFD9` = action / focus / "working" accent; gold `#FFCC49` and violet `#B077DD` = secondary signals (RAG, badges).

### Light mode (default)

```scss
// Background & surfaces
--bg:            #F6F7F9;  // app background, behind panels
--surface:       #FFFFFF;  // panels, cards, sidebar
--surface-2:     #F0F2F5;  // hover, nested areas
--surface-3:     #E6EAEE;  // pressed, thick dividers

// Text
--text:          #1C2A36;  // main (very dark teal, readable)
--text-muted:    #5B6B7B;  // secondary, meta, paths
--text-faint:    #8A99A8;  // watermark, placeholders

// Borders
--border:        #E4E8ED;
--border-strong: #D2D9E0;

// Brand & accents
--primary:       #203D52;  // teal blue: active header, active workspace, link
--primary-soft:  #E8EEF2;  // active workspace background (very diluted teal)
--accent:        #2BB5C2;  // action cyan (AA contrast on white)
--accent-strong: #3ECFD9;  // full cyan: hover, streaming
--accent-soft:   #DCF6F7;  // focus / session badge background

--gold:          #E0A93A;  // gold AA on white: "modified"
--gold-soft:     #FFF3D6;
--violet:        #9A63C7;  // violet AA on white: RAG, "created"
--violet-soft:   #F0E4FA;

// Semantic
--success:       #2E9E74;
--danger:        #D64545;
--danger-soft:   #FBE6E6;
--warning:       var(--gold);

// Anubis neutrals (scale) -> map to surface/text above
--neutral-lowest:  #FFFFFF;
--neutral-lower:   #F6F7F9;
--neutral-low:     #F0F2F5;
--neutral-medium:  #C6CFD8;
--neutral-high:    #8A99A8;
--neutral-higher:  #5B6B7B;
--neutral-highest: #1C2A36;
```

### Dark mode

```scss
--bg:            #131F28;  // very dark teal, not pure black
--surface:       #1B2C38;
--surface-2:     #23384A;
--surface-3:     #2C4254;
--text:          #E8EEF2;
--text-muted:    #9FB0C0;
--text-faint:    #6E8195;
--border:        #2C4254;
--border-strong: #3A5266;
--primary:       #3ECFD9;  // cyan becomes primary in dark (more readable)
--primary-soft:  #1E3A44;
--accent:        #3ECFD9;
--accent-strong: #5DE2EB;
--accent-soft:   #1E3A44;
--gold:          #FFCC49;
--gold-soft:     #3A2F12;
--violet:        #C99BED;
--violet-soft:   #2E1F44;
--neutral-lowest: #131F28;
--neutral-lower:  #1B2C38;
--neutral-low:    #23384A;
--neutral-medium: #3A5266;
--neutral-high:   #6E8195;
--neutral-higher: #9FB0C0;
--neutral-highest:#E8EEF2;
```

## 2. Typography

- **UI / titles / body**: `Varela Round` (load the webfont; fallback `Inter`, `system-ui`, `sans-serif`). Varela Round only has 400; we simulate "700" via `font-weight: 700` with `Inter` 700 fallback for titles since Varela Round has no native bold. Alternative: `Quicksand` (bold available, same rounded feel) for titles. **Decision**: body in Varela Round 400, titles in `Quicksand` 600/700 (rounded, graspable, has real bold). Fallbacks `Varela Round, system-ui`.
- **Code / diff / paths**: `JetBrains Mono`, fallback `ui-monospace, SFMono-Regular, Menlo, monospace`.

Scale:

| Role | Size | Weight | Font |
|---|---|---|---|
| display (onboarding) | 2rem / 32px | 700 | Quicksand |
| h1 (workspace title) | 1.4rem / 22px | 700 | Quicksand |
| h2 | 1.15rem / 18px | 700 | Quicksand |
| h3 (sidebar section) | 0.8125rem / 13px | 700, uppercase, letter-spacing 0.06em | Quicksand |
| body (chat) | 0.9375rem / 15px | 400 | Varela Round, line-height 1.6 |
| meta (dates, paths) | 0.8125rem / 13px | 500 | Varela Round |
| code | 0.85rem / 13.6px | 400 | JetBrains Mono |

Radii: `--r-sm: 8px`, `--r-md: 12px`, `--r-lg: 16px`, `--r-pill: 999px`. Soft shadows: `--shadow-1: 0 1px 2px rgba(28,42,54,0.06)`, `--shadow-2: 0 6px 24px rgba(28,42,54,0.10)`.

## 3. Three-column layout

```
+---------------------------------------------------------------+
| Title bar Tauri (40px) : [logo Workproba]  ·  {workspace}  ·  [theme] |
+----------+--------------------------------------+--------------+
| Sidebar  |              Center                  |   Files      |
| 268px    |  (chat, max-width 760px centered)    |   320px      |
| rail 56  |                                      |   collapsible|
| collapsible|                                    |   Cmd/Ctrl+B |
+----------+--------------------------------------+--------------+
```

- **Left sidebar**: 268px (min 240, max 320). Collapsible to 56px icon rail (never fully hidden). Contains, top to bottom: active workspace header + transient switcher; "Conversations" section (new conversation + list grouped by date); sidecar status footer.
- **Center**: fluid, `min-width 480px`. Centered chat surface, `max-width 760px`, generous margins (48px side on desktop). Input area anchored at bottom, `max-width 760px` aligned with chat.
- **Right files**: 320px (min 240, max 400). Collapsible, state remembered per workspace. Filter bar at top, virtualized tree below, footer = indexing bar (if large folder).
- **Empty states**: see `lea-ux.md` §3 (always an action, never "empty").

Responsive desktop webview: below 1100px, the files panel auto-collapses (shortcut to reopen). Below 820px, sidebar switches to 56px rail.

## 4. Key components (to create/style on Quasar)

### 4.1 `WorkprobaTitleBar` (window title bar, custom Tauri decoration)
40px, `--surface` background + bottom `--border`. Left: "Workproba" logotype in Quicksand 700, `--primary` color (light) / `--accent` (dark). Center: workspace name + truncated path, `--text-muted`. Right: theme toggle + window buttons (reduce/min/close via Tauri `window` API). Window drag zone (`data-tauri-drag-region`).

### 4.2 `WorkspaceSidebar` (left)
- **Active workspace header**: `--surface-2` card, `--r-md` radius, 10px 12px padding. Folder icon (Lucide `folder`, `--accent` color), name (Quicksand 700, 1 line ellipsis), truncated path (meta, `--text-faint`). `chevron-down` indicates "click to switch". On click: transient menu (`q-menu`) listing recent workspaces (icon + name + truncated path), active item highlighted `--accent-soft` + left `--accent` border, and a `+ Open another folder…` entry.
- **Conversations section**: h3 title "CONVERSATIONS" + icon button "New conversation" (`message-square-plus`) on the right. Scrollable list, grouped by date (h3 labels "Today", "This week", "Older"). Item: 8px 10px padding, `--r-sm` radius, 1 line ellipsis title, date meta below. Hover `--surface-2`. Active `--accent-soft` + `--text` + 3px left `--accent` border. During streaming: pulsing cyan dot left of title.
- **Status footer**: 1 line, dot icon (cyan connected / gray idle / cyan pulse "working"), meta label.

### 4.3 `ChatSurface` (center)
Reuse of existing `front/src/components/chat/`, restyled: full-width bubbles (not floating bubbles, Claude style), small assistant avatar (Improba "W" monogram on `--accent-soft` pill), user messages aligned with `--surface-2` background `--r-lg` radius. Collapsible tool-call cards in "file read" / "file modified" style (Léa's human labels). RAG sources: `--violet` violet pills. Input area: auto-expanding textarea, `--r-lg` radius, `--border` border, `--accent` focus. "Send" primary button `--accent`, becomes "Stop" (`square` icon) during streaming. Streaming status above message: "The agent is thinking…" / "The agent is reading `x`…".

### 4.4 `FileExplorer` (right)
- **Filter bar**: input with `search` icon (Lucide), placeholder "Filter files…", `Cmd/Ctrl+P` focus. Always visible.
- **Virtualized tree**: `vue-virtual-scroller` `RecycleScroller`, row height **26px**, depth via left padding `depth * 16px` (no nested DOM). Directories first, then files, case-insensitive sort. Lucide icons by type (`folder`, `file-text`, `file-code`, `file-image`, `file-spreadsheet`, `file-pdf`…). `chevron-right`/`chevron-down` on directories (click = expand/collapse, not on label).
- **Session dot**: `--accent` cyan 6px pill right of node if touched during session (single signal, tooltip "created" / "modified"). Auto-expand + `--accent-soft` highlight fade-out 3s.
- **Actions**: double-click label = open in OS (Tauri `open`). Right-click = "Reveal in Finder/Explorer", "Open" menu. "Reveal" button on hover.
- **ARIA**: `role="tree"`, `treeitem`, keyboard navigation `↑/↓/→/←/Enter`.
- **Indexing footer**: thin bar + "Indexing N files…" label during initial index.

### 4.5 Micro-interactions (Improba breathing)
- Transitions: `transition: 180ms cubic-bezier(0.4, 0, 0.2, 1)` on hover/active.
- "Breath": "working" status pulses `opacity 0.6 → 1` over 1.6s ease-in-out.
- Assistant message appearance: fade + translateY 4px over 220ms.
- Tree expand: chevron rotation 150ms, children slide-down 180ms.
- No blinking, no jumps. Everything is smooth.

## 5. Improba soul touch

- **Generous rounded shapes** (`--r-lg` 16px on cards and input, `--r-pill` on badges/status).
- **Cyan = breath**: the only color that "breathes" (streaming pulse, focus, session dot). The rest is neutral. One vivid color, never scattered.
- **Breathing room**: 48px side margins, generous padding, line-height 1.6, lots of white space.
- **Mini logotype** in title bar + assistant "W" monogram: discrete but constant brand anchor.
- **Native window title**: "Workproba, {workspace}" (first word = brand in OS taskbar).

## 6. Implementation plan

1. **Design tokens**: `front/src/css/workproba-tokens.scss` (light/dark variables) + global import. Load Varela Round + Quicksand + JetBrains Mono webfonts.
2. **Three-column layout**: `front/src/layouts/WorkprobaLayout.vue` (replaces `StandardLayout` for desktop target) + `WorkprobaTitleBar.vue`.
3. **Left sidebar**: `WorkspaceSidebar.vue` + `WorkspaceSwitcher.vue` + `ConversationList.vue` (wired to `workspaceSession` + `useProject`).
4. **Center chat**: rewire existing `ChatView` in the new layout + restyle.
5. **Right FileExplorer**: `FileExplorer.vue` + `useFileTree` (store) + Rust watcher (`desktop/src-tauri/src/commands/fs_watch.rs`, `notify` crate).
6. **Empty states & onboarding**: first launch screen, empty tree / unreachable sidecar states.

The Rust FS watcher (step 5) is the most technical piece: new Rust module + Tauri events + frontend store + 150ms debounce + partial reconciliation.
