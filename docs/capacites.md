# Capacités activables

> **Last updated:** 21/07/2026  
> **Audience:** end users (mode guidé)

## What are capabilities?

**Capabilities** are optional features you can turn on to extend Workproba. They are listed in the **Capabilities** hub (button in the title bar).

You do not need to know about technical plugins or extensions to use them in guided mode.

### Local capabilities

| Capability | What it adds | Where it lives after activation |
|---|---|---|
| **Workproba Cloud** | Connect this computer to your organization (login / invitation), org LLM, gateway for sub-capabilities | Right panel, Workproba Cloud tab |
| **Business perspectives** (Regards métier) | Expert-style opinions, discussions, cross-perspectives | Side panel and central area |
| **Web navigation** | Browse pages from Workproba with guided agent help | Right panel, Browser tab |

### Sub-capabilities (under Workproba Cloud, collapsible)

| Sub-capability | Role |
|---|---|
| **Project management** (`projects`) | Local library + shared projects via Cloud |
| **Managed** (e.g. **Ihora**) | Org-authorized services from `GET /connectors` |

The Capabilities hub lists **Workproba Cloud first**. Nested items open in a **collapsible** zone (compact cards, scrollable when many). Guided mode hides technical stubs (`echo`, `ihora.shaped`).

**Cloud setup:** account login (`POST /devices/login` → User JWT, exchanged by the sidecar into a durable DeviceBearer `wp_dev_*`) and device enroll (`POST /devices/join` → DeviceBearer) both leave a `wp_dev_*` on disk. Both are available from the onboarding wizard and Settings → AI Models.

| **Mount sync** (advanced) | Technical NAS bridge via `ProjectSyncPort` ; deprecated product path, **blocked when enrolled** | Advanced mode only ; not a Capabilities card |

## Projects and sources of truth

| Concept | Source of truth | What it is not |
|---|---|---|
| **Solo project / library** | **Local machine** (`app_data/plugins/workproba.projet/`) | A shared project ; cloud is not the SoT |
| **Shared project** | **Cloud** (control plane + S3) ; list/publish/open/republish via enrolled device | NAS mount, mirror push/pull, or local folder as SoT |
| **Local copy (shared)** | Disposable cache on the workstation (opened on demand) | A second source of truth |
| **Mount sync** | Technical NAS bridge (`ProjectSyncPort`) ; advanced only, **blocked when enrolled** | A shared project ; deprecated as a guided product path |

Solo projects stay **local SoT** (on the machine). Shared projects and **managed capabilities** require cloud enrollment (join org via `join_token` ; DeviceBearer stored locally). Once enrolled, mirror push/pull is refused ; use publish and republish instead.

Managed capabilities use Improba Cloud Mode A: the agent calls `invoke_managed_connector` (Human Approval Gate `external_send`) ; the cloud relays to org-allowed services (`echo`, `ihora.shaped` stub, `ihora` HTTP). The desktop does not send `device_id`, `subject_id` or `org_id` in the invoke body. Bidirectional sync with conflict resolution is **out of scope** as a product flow. See [architecture-cloud.md](../../workproba-improba/roadmaps/architecture-cloud.md).

## How to activate

1. Click **Capabilities** in the title bar.
2. **Workproba Cloud** appears first. Enable / configure it to enroll your organization.
3. Open **Sub-capabilities** (collapsible) under Cloud: **Project management**, then any org-managed items (e.g. **Ihora**). Compact cards; scroll when the list is long.
4. Other top-level cards: Regards métier, Navigation web.

Managed items are controlled by the organization (no local disable toggle). Disabling Workproba Cloud also turns off nested Project management (parent cascade).

To turn a top-level local capability off, use **Disable** on its card.

## What is not a capability?

- **Web search** when the Imp looks up facts on the public web: automatic when your engine and network policy allow it. Sources appear as links under assistant messages.
- **Memory**, **conversations**, and **file tools**: always available in your **space** (local folder).
- A second desktop « connector » for Ihora or other org services: those are **managed capabilities** under Workproba Cloud, not separate Capabilities cards at the top level.

## Advanced mode

In **Settings → Extensions**, administrators can see technical plugin details, permissions, and local plugin installation (developer builds only). Technical stubs (`echo`, `ihora.shaped`) can appear as managed capabilities under Workproba Cloud.

See also: [plugins.md](./plugins.md) (honest technical status), [capacites-ux-v2.2.md](../../workproba-improba/roadmaps/capacites-ux-v2.2.md) (product spec).
