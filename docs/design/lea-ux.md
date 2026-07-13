# Workproba, UX Proposal

Author: Léa (UX strategist), debate with Inès (lead designer).

## 1. Information architecture and hierarchy

### Choice: a single left sidebar, two levels deep, not two panels.

Sidebar structure, top to bottom:

1. **Sidebar header**: the active workspace (folder icon + name), clickable, opens a **recent workspaces switcher** (transient menu, not a permanent panel). "Open a folder" button at the bottom of this menu.
2. **"Conversations" section** of the active workspace: scrollable list, grouped by date (Today / This week / Older), like Claude/Cursor. "New conversation" button at the top of the section.
3. **Sidebar footer**: compact status (AI sidecar connected, RAG memory indexed), reduced to one line.

The center remains **the conversation**. The right side remains **the workspace file tree**.

### Why not two separate panels (workspaces | conversations)?

For a non-coder, juggling between two lists requires knowing "where I am in the hierarchy." Cursor can afford that: its audience lives in an editor 8 hours a day. We cannot. A single panel that **changes semantic level** with a clear way back (the workspace name at the top) means fewer surfaces to scan, a single column to read. The workspace switcher is a **menu** (transient), not a permanent panel: you open it, you choose, it disappears. The active workspace remains the stable anchor.

### Why not put everything in a single tree (workspace > conversations)?

Workspaces are **physical folders** (few, ~5 to 20 max), conversations are **numerous objects** (dozens per workspace). Mixing the two creates unjustified depth and hides conversations under a collapsed node. We separate them: workspaces = flat switcher, conversations = dedicated list.

Mental model: *one project folder (workspace), several discussions (conversations) inside it.*

## 2. Key flows

### 2.1 First launch (no workspace)

- Centered window, Improba brand background, **single large action area**: "Open a folder to get started."
- Short subtitle: "Workproba works on your local files. Nothing leaves your machine except what you send to the AI."
- Single primary button: "Choose a folder" (native Tauri picker).
- No empty recent list displayed: we never show an empty "there is nothing" state, we show the action.
- On the right: empty tree with an icon and the text "Your file tree will appear here."

### 2.2 Opening a new folder

1. User clicks "Choose a folder" (onboarding) or the button in the workspace switcher.
2. Native Tauri picker. The user confirms a folder.
3. Frontend response: we generate a UUID, create `~/.local/share/fr.improba.workproba/workspaces/{uuid}/`, index the tree (Rust, watch_FS started).
4. Transient feedback: "Folder 'Devis 2026' opened" (2 s toast).
5. **First conversation created automatically**, titled "New conversation", focus in the input area. Inline micro-onboarding in the first assistant message: "I'm ready. Describe what you want to do with the files in this folder."
6. The right-hand tree populates.

### 2.3 Switching between recent workspaces

1. User clicks the **active workspace at the top of the sidebar**.
2. Transient menu: list of recent workspaces (icon + name + truncated path), active item highlighted, "Open another folder…" entry.
3. Click on an item: menu closes, workspace loads, conversations reload, right tree refreshes. The active conversation of the workspace is restored (the last opened, or the first if never visited).
4. No confirmation: reversible context change.

### 2.4 Starting a new conversation in the current workspace

1. "New conversation" button at the top of the conversations section (and `Cmd/Ctrl+N` shortcut, shown in tooltip, not required).
2. The current conversation is **paused** (scroll state + messages persisted in memory and on disk).
3. A new empty conversation takes the center, provisional title "New conversation", focus in the input.
4. The title renames automatically after the first user/assistant exchange (short AI summary), like Claude. The user can rename it on double-click.

### 2.5 Resuming an existing conversation

1. Click on a conversation in the list.
2. Load from disk (Tauri). During loading (<200 ms): keep the previous conversation displayed with a light veil, not a blank screen.
3. Restore **scroll position** and message selection. We persist `scrollTop` + `activeMessageId` in conversation metadata.
4. The right tree stays the same (it's the workspace), but we can optionally **highlight files already touched in this conversation** (discrete toggle).

### 2.6 Interacting with the file tree

- **Expand/collapse**: click on the node chevron (not the label, to avoid accidental opening). `→`/`←` keyboard for expand/collapse.
- **Open in the OS**: double-click on the label = open the file with the system's default application (Tauri `open`). The most "non-coder" action: we don't want a built-in code editor, we want "open my quote.docx in Word."
- **Reveal in Finder/Explorer**: context menu (right-click) + "Reveal" button on hovered node.
- **Filter**: filter bar at the top of the tree (always visible). Fuzzy filter, instant, with parent path shown in watermark to disambiguate.
- **Keyboard shortcuts**: `Cmd/Ctrl+P` opens the filter and focuses directly. We don't require shortcuts, we offer them.

### 2.7 While the agent is working (streaming + tool calls)

The most anxiety-inducing moment for a non-coder. Relief is the number one criterion.

- **Center**: the assistant message builds in streaming, soft typing cursor. Above the block, an animated status: "The agent is thinking…" then "The agent is reading `devis.pdf`…" then "The agent is modifying `facture.xlsx`…" (human labels, not `tool_call:read_file`).
- **Right (tree)**: files **touched during the session** receive a discrete badge (a colored Improba dot for "recently created/modified"). The node auto-expands to be visible, and a temporary highlight (fade out over 3 s) signals the change. No blinking, no violent scroll jumps.
- **Sidebar**: the active conversation shows an activity dot next to its title.
- **Sidebar footer**: sidecar status goes from "Connected" to "Working…" with a subtle pulse.
- The user can **stop** ("Stop" button replaces "Send" during streaming). Stop always visible and accessible.

## 3. States and feedback

### Empty states (never "empty", always "action")

- **No workspace**: welcome screen described in 2.1.
- **Workspace open, no conversation**: impossible by design (we create the first conversation on open). We eliminate an empty state.
- **Empty workspace folder** (no files): right tree shows "This folder is empty. Drag files here or ask the agent to create some." With a "Create a first file" button. We turn emptiness into an invitation.

### Loading

- Workspace change: light veil on the previous one (no blank screen).
- Initial tree indexing (large folder): thin bar at the bottom of the tree, "Indexing 12,480 files…", disappears when done. Never a full-screen spinner.

### Errors

- **AI sidecar unreachable**: discrete banner at the bottom of the conversation (not full screen), "The agent is unreachable at the moment. Retrying in 3 s…" with "Retry now" button. The input area stays active. We never block input.
- **File deleted between operations**: non-blocking toast "The file no longer exists" + tree updates via watch.
- **Folder permission denied**: clear message, "Workproba does not have access to this folder", with a link to short documentation.

### Streaming

- "The agent is thinking…" indicator before the first token (not an empty message that appears then fills). Distinguish "thinking" (nothing yet) and "writing" (tokens arriving), it reassures.

## 4. Right file tree, "polished and performant"

### Data model (frontend side)

An in-memory tree, flat by depth, indexed by absolute path:

```ts
type TreeNode = {
  path: string // absolute, unique key
  name: string
  isDir: boolean
  depth: number
  children?: string[] // child paths, lazy loaded
  loaded: boolean // children already fetched?
  sessionState: 'idle' | 'created' | 'modified' // during the session
}
```

A `Map<string, TreeNode>` + an array of visible paths (corresponds to expanded nodes), used for virtualization.

### Virtualization

vue-virtual-scroller already available: we only render visible nodes + margin. For 50,000 files, smooth scrolling. Fixed row height (26 px), depth rendered by calculated left padding, not nested DOM (performance and scroll simplicity gain).

### Real-time updates

- Rust side: a filesystem watcher per workspace (`notify`). We emit typed Tauri events: `fs:create`, `fs:modify`, `fs:delete`, `fs:rename`.
- Frontend side: a Pinia store consumes events, updates the `Map`, and only re-renders the affected branch (ancestors of the touched path). No global re-indexing.
- **Debounce**: we group bursts (a `git checkout` touching 500 files should not cause 500 UI updates). 150 ms window, then a single reconciliation pass.
- **Stable sort**: directories first, then files, case-insensitive alphabetical. "Recently modified files at top" option in a tree preferences menu (offered, not default).

### Lazy expand

A folder's children are never loaded until the node is expanded. On workspace open, we only load **the first level** + any previously expanded folders (persisted in workspace metadata). For a folder with 10,000 entries, we paginate child rendering via the virtualizer, no visible logical pagination.

### Instant search/filter

- Input in the filter bar: fuzzy filter on name, flat result display with parent path in gray watermark. Escape filter mode with `Esc`, return to expanded tree.
- During filtering, matched nodes auto-expand, as do their ancestors.
- Counter: "12 results".

### Keyboard accessibility

- The tree is an ARIA `tree` with `treeitem`. Navigation `↑/↓`, expand/collapse `→/←`, open `Enter`, reveal `Cmd/Ctrl+R` (offered).
- Visible focus: Improba focus ring, never removed.

### Session indicators

- `created`: green "new" badge.
- `modified`: orange "modified" badge.
- Reset on conversation change (option: "Keep highlighting between conversations" in preferences).

## 5. Brand and orientation "I'm in Workproba"

Without overloading, three anchor points:

1. **Native window title**: "Workproba, {workspace name}". The first word = the brand, always there in the OS taskbar. Free and powerful.
2. **Compact logo at the top of the sidebar**: a mini Improba logotype (not a large banner), next to the active workspace name. This is the "I'm in the right app" anchor.
3. **Color accent**: a single Improba accent color, used for focus, session badges, "working" status, primary send button. Just one. Never scattered.

Micro brand element: the assistant signature in messages (small avatar + first name), creating a human presence consistent with the brand. We're not a cold tool, we're a workshop with someone inside.

## 6. UX risks and trade-offs

- **Density vs breathing room**: dense file tree (24 px) maximizes information but can intimidate a non-coder. Proposed compromise: 26 px. Design decision (Inès).
- **Persistent vs hideable tree**: for small screens (13"), the right tree can clutter. **Collapsible** panel with state remembered per workspace, `Cmd/Ctrl+B` shortcut (offered, not required). The left sidebar does not hide: it's the stable anchor.
- **Keyboard shortcuts for non-coders**: offer them without requiring them. All primary buttons visible and labeled. `Cmd/Ctrl+K` command palette? Powerful but potentially intimidating. Opinion: yes, with clear labels ("New conversation", not "chat.new"), it becomes a discovery aid rather than an expert hideout.
- **Automatic conversation renaming**: convenient but can destabilize. Discrete rename undo.
- **Highlighting files touched during AI work**: auto-expand + fade out. To validate on a real test folder.

## 7. Trade-offs to submit to Inès

1. **Single two-level sidebar (my choice) vs two workspaces/conversations panels**: validate the "transient switcher + dedicated conversations list" model, or test both in a quick mockup with 3 non-coders?
2. **Session badge in the tree (green "new" / orange "modified")**: keep both levels, or simplify to a single "touched during session" signal to reduce visual load?
3. **`Cmd/Ctrl+K` command palette**: offer it as a discovery aid (clear labels), or reserve it for a future release to avoid overloading first launch?
