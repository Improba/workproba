# Capacités activables

> **Last updated:** 17/07/2026  
> **Audience:** end users (mode guidé)

## What are capabilities?

**Capabilities** are optional features you can turn on to extend Workproba. They are listed in the **Capabilities** hub (button in the title bar).

You do not need to know about technical plugins or extensions to use them in guided mode.

| Capability | What it adds | Where it lives after activation |
|---|---|---|
| **Business perspectives** (Regards métier) | Expert-style opinions, discussions, cross-perspectives | Side panel and central area |
| **Projects and deliverables** | Publish documents from your space into a local project library | Right panel, Project tab |
| **Web navigation** | Browse pages from Workproba with guided agent help | Right panel, Browser tab |
| **Improba Cloud** | Join org, managed connectors (`echo`, `ihora.shaped` stub), shared projects, enterprise regards | CloudPanel under Projects |
| **Mount sync** (advanced) | Technical NAS bridge via `ProjectSyncPort` ; deprecated product path, **blocked when enrolled** | Under Projects (advanced mode only) |

## Projects and sources of truth

| Concept | Source of truth | What it is not |
|---|---|---|
| **Solo project / library** | **Local machine** (`app_data/plugins/workproba.projet/`) | A shared project ; cloud is not the SoT |
| **Shared project** | **Cloud** (control plane + S3) ; list/publish/open/republish via enrolled device | NAS mount, mirror push/pull, or local folder as SoT |
| **Local copy (shared)** | Disposable cache on the workstation (opened on demand) | A second source of truth |
| **Mount sync** | Technical NAS bridge (`ProjectSyncPort`) ; advanced only, **blocked when enrolled** | A shared project ; deprecated as a guided product path |

Solo projects stay **local SoT** (on the machine). Shared projects and **managed connectors** require cloud enrollment (join org, `device_id`). Once enrolled, mirror push/pull is refused ; use publish and republish instead. Managed connectors use Improba Cloud Mode A (`invoke_managed_connector`, builtins `echo` and `ihora.shaped` stub). Bidirectional sync with conflict resolution is **out of scope** as a product flow. See [architecture-cloud.md](../../workproba-improba/roadmaps/architecture-cloud.md).

## How to activate

1. Click **Capabilities** in the title bar.
2. Pick a capability card.
3. Use **Enable and open** to activate it and jump to its home surface.

To turn a capability off, open the hub again and use **Disable** on an active card.

## What is not a capability?

- **Web search** when the Imp looks up facts on the public web: automatic when your engine and network policy allow it. Sources appear as links under assistant messages.
- **Memory**, **conversations**, and **file tools**: always available in your **space** (local folder).

## Advanced mode

In **Settings → Extensions**, administrators can see technical plugin details, permissions, and local plugin installation (developer builds only).

See also: [plugins.md](./plugins.md) (honest technical status), [capacites-ux-v2.2.md](../../workproba-improba/roadmaps/capacites-ux-v2.2.md) (product spec).
