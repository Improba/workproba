# Plan : Agents métier, Regard et config par tenant

> **Statut :** plan d'action agents métier — **P0–P4 livrés** + polish streaming handoff (06/08/2026)
> **Date :** 06/08/2026 (vocabulaire Agent métier ; amendement 27/07 ; impl P0–P4)  
> **Décideur :** Syl  
> **Rôle :** SoT du **prochain chantier** (panels d'outils, runner, sync catalogue enrichi). Complète [roadmap-v2.md](../../workproba-improba/roadmaps/roadmap-v2.md) (Mode A / ports / H0–H1), ne le remplace pas.  
> **Noms de code :** `SpecialistRun`, `SpecialistRegistry`, `specialists[]`, `summon_specialist` = jargon technique provisoire ; vocabulaire produit = Agent métier / Regard / Agent d'entreprise.  
> **Liens :** [intention.md](./intention.md) · [intention Improba](../../workproba-improba/intention.md) (amendement 06/08 Agents métier) · [glossaire](../../workproba-improba/roadmaps/glossaire.md) · [positionnement cloud / agents métier](../../workproba-improba/roadmaps/positionnement-cloud-regards.md) · [architecture cloud](../../workproba-improba/roadmaps/architecture-cloud.md) · [capacites.md](./capacites.md) · [plugins.md](./plugins.md)

---

## 1. Problème

Via Workproba Cloud, beaucoup d'outils seront **actifs par défaut** (RH lecture, politiques entreprise lecture, métier lecture/écriture, administratif). Les injecter en vrac dans le tour de l'assistant principal ne scale pas :

- confusion d'outils proches ;
- latence / coût de contexte ;
- risque d'écriture trop précoce ;
- UX Human Approval Gate saturée.

Le filtre « capacité on/off » par espace ne suffit plus si le tenant active volontairement un large inventaire.

---

## 2. Intention produit (rappel)

```text
User ↔ Assistant / Imp (chat principal)
         ├─ mobilise des Agents métier (panels d'outils selon profil)
         └─ User peut solliciter le Regard d'un Agent métier
               = même agent, mode lecture / avis
```

| Concept | Rôle | Outils |
|---|---|---|
| **Assistant** (Imp) | Face à l'utilisateur ; orchestre | fichiers, mémoire, délégation |
| **Agent métier** | Profil métier (RH, juridique, …) avec panel d'outils | lecture, et éventuellement écriture selon profil |
| **Regard** | Mode consultatif d'un agent métier (UI ou via l'assistant) | **read-only** : consulter, expliquer, recommander |

Principes :

- Agent métier = sous-agent borné (doctrine + allowlist + contrat de sortie), pas un second chatbot généraliste ;
- capacités cloud = **inventaire** ; l'agent métier **sélectionne et discipline** un sous-ensemble ;
- pas « 1 app cloud = 1 agent métier » ;
- regards croisés = plusieurs agents métier en mode Regard ;
- écritures : agent métier opératoire et/ou assistant + Human Approval Gate ; **jamais** via le bouton Regard ;
- code interne peut rester `personas` ; UI produit : Agent métier / Regard / Agent d'entreprise (gouvernance).

---

## 3. Source de vérité : config par tenant

Le tenant (organisation) configure ses agents métier. Workproba desktop **consomme** et met l'UI à jour.

| Acteur | Où | Quoi |
|---|---|---|
| **Org admin** | Console Improba Cloud (`/adminspace`) | Agents métier : doctrine / consignes, contrat de sortie, **panel d'outils** |
| **Org admin** | `/adminspace/connectors` (déjà là) | Inventaire : quels connecteurs l'org autorise |
| **User desktop** | Workproba | Reçoit le catalogue org, voit, mobilise (Regard / assistant). Ne définit pas les agents d'entreprise. |

```text
Tenant (org)
  1. Allowlist connecteurs (existant, fail-closed si vide)
  2. Définit Agent métier RH :
       - paramètres (nom, doctrine, format, modes regard / opératoire)
       - outils cochés parmi tools[] des connecteurs autorisés
  3. Publie une version signée

Poste Workproba (enrollé)
  ← pull catalogue (sync regards)
  → capacité locale « Regards » / plugin personas active (sinon catalogue non mobilisable)
  → UI agents métier / regards se met à jour
  → runtime n'expose que le panel au SpecialistRun
```

Prérequis desktop : compte cloud connecté **et** capacité / plugin regards active. La sync catalogue ne remplace pas l'activation de la capacité.

### Deux couches à ne pas fusionner

1. **Inventaire org** (existant) : quels connecteurs existent pour cette org.  
2. **Profil agent métier** (à ajouter) : pour *cet* agent, quels tools + quelle doctrine.

Hub Capacités ≠ liste des agents métier : capacités = tuyaux ; agents métier = profils métier paramétrés par le tenant.

### Couches d'autorisation effectives

**À la publication (cloud) :** chaque ref `{connector_id, tool}` doit exister dans le `tools[]` d'un connecteur **allowlisté pour l'org**. Sinon refus.

**Au runtime (desktop),** un tool managed n'est enregistré / appelable par un `SpecialistRun` que s'il passe :

1. connecteur dans le snapshot de tour (`managed_allowed_connector_ids` : déjà le résultat de allowlist org ∩ overrides user ∩ wanted espace ∩ enable local ∩ entitlements cloud plugin) ;
2. tool présent dans le panel de l'agent métier (allowed − forbidden) ;
3. filtre de mode (Regard → uniquement tools du cache avec `effect: read`) ;
4. filtre `visibility` selon `ui_mode` (guided / standard / advanced), comme aujourd'hui pour `managed__*`.

La couche org n'est pas re-vérifiée ad hoc dans le runner : elle est déjà matérialisée dans `GET /connectors` + construction du snapshot. Le publish admin évite les panels incohérents en amont.

---

## 4. État actuel (faits)

| Domaine | Existe | Manque |
|---|---|---|
| Personas / Regards desktop | avis LLM **sans outils managed**, UI SSE (`ask` / meeting / discuss), mémoire projet optionnelle, sets locaux + catalogues signés (`personas[]`) | panel d'outils managed, doctrine structurée consommée |
| Managed tools | cache, snapshot tour, noms `managed__{connector}__{tool}`, HAG sauf `effect: read`, fallback `invoke_managed_connector` | exposition progressive, allowlist par profil |
| Cloud connectors | allowlist org + overrides user, `GET /connectors` avec `tools[]` (`effect`, `visibility`, `input_schema`) | lien vers agents métier |
| Cloud agents d'entreprise | draft / publish / revoke ; payload peu validé ; `SignedBundle` | signer n'embarque que `personas[]` ; admin = JSON brut ; pas de picker tools |
| Schéma `regard-enterprise.schema.json` | `doctrine`, `tools.allowed/forbidden` en **string[]** (outils « locaux » type search_kb), `output_contract` au niveau **d'un** regard | non branché au signer/runtime ; format string[] **incompatible** avec les refs managed ciblées ; pas de `specialists[]` / `agents[]` |
| Lien agents ↔ tools | aucun | allowlist par agent métier |
| Desktop SignedBundle | dataclass avec `personas` obligatoire | champ `specialists` à ajouter (dual-read) |

Surfaces utiles :

- Desktop : `workproba_personas/`, `workproba_cloud/plugin.py` (`sync_managed_regards`), `capabilities_turn.py`, `ManagedAgentsPort` (code actuel : `ManagedRegardsPort`), `POST /plugins/cloud/sync-regards`, CloudPanel
- Cloud : `/adminspace/regards`, `/adminspace/connectors`, `GET /catalogs/regards`, `regard-bundle.signer.ts`

Outils agent personas actuels : `ask_personas`, `simulate_meeting` (pas de `summon_*`).

---

## 5. Architecture cible

```text
workproba-cloud (par org)
  connectors[]     → inventaire tools (effect, visibility, input_schema)
  specialists[]    → profils dans le bundle signé (doctrine + allowlist + output_contract)
       │            (cible produit : agents métier ; clé JSON peut évoluer specialists[] / agents[])
       │
       ▼ pull / sync (DeviceBearer)
Desktop
  ManagedAgentsPort (code actuel : ManagedRegardsPort, étendu) + cache connectors
       │
User ↔ Assistant
       │  tools cibles: summon_specialist (+ locaux fichiers / mémoire)
       │  sans catalogue managed__* plat sur le parent (cible après P4)
       ▼
SpecialistRun(mode=regard|operative)
       │  tools managed = panel ∩ couches runtime §3 ∩ filtre mode
       ▼
invoke_managed_connector_impl  (HAG inchangé pour write)
       ▼
RemoteCapabilityGateway → POST /connectors/:id/invoke
```

### Composants desktop

1. **SpecialistRegistry** : sets locaux + catalogues managés enrichis (évolution de la résolution personas / `ManagedAgentsPort`)  
2. **ToolAllowlistResolver** : refs `{connector_id, tool}` → `managed__…` ; intersection runtime §3  
3. **SpecialistRun** : un runner, deux modes  

Pas de second chemin d'invoke write : réutiliser `invoke_managed_connector_impl`.

### Runtime : un seul runner

| Mode | Entrée | Tools managed | HAG |
|---|---|---|---|
| **Regard** | UI regard, ou délégation avis | panel ∩ `effect: read` uniquement | non applicable (aucun write enregistré) |
| **Opératoire** | `summon_specialist` | panel complet ∩ couches runtime | oui, sur `effect != read` |

Tools du panel absents du snapshot / cache → `degraded_tools[]` (honnête), pas d'appel fantôme.

**Outils locaux (fichiers / mémoire) :** hors panel tenant. En mode Regard, conserver le comportement actuel optionnel (mémoire projet en lecture), **jamais** d'outils locaux d'écriture. Tranché : le panel signé ne décrit que les tools **managed** cloud.

### Ce que voit l'assistant (cible après P4)

- tools locaux (fichiers, mémoire, …) ;
- `summon_specialist(specialist_id, task, mode?)` ;
- **aucun** catalogue `managed__*` plat sur l'agent parent ;
- **aucun** fallback `invoke_managed_connector` sur le parent (sinon contournement du modèle).

Pendant P1–P3, le dump `managed__*` (et le fallback) peuvent rester sur le parent ; leur retrait est un livrable **P4**.

### Meeting / regards croisés

- **Regards croisés / ask multi** : N× `SpecialistRun` en mode Regard (lecture seule), synthèse côté Imp / orchestrateur.  
- **`simulate_meeting` / vue réunion** : hors scope outil managed jusqu'à P4+ ; reste avis texte comme aujourd'hui, sauf décision ultérieure de brancher le même runner Regard par tour de parole.

---

## 6. Contrat de données cloud

### Évolution par rapport à l'existant

Aujourd'hui : un `RegardEnterprise` publié → `SignedBundle` avec `personas[]` seulement (cloud et desktop).

**Décision retenue (ferme) :** un catalogue versionné = **N agents métier** via `specialists[]` (ou évolution `agents[]`) dans payload + bundle ; dual-read `personas[]` pour les vieux clients / bundles.

Le schéma `regard-enterprise.schema.json` (un document = un regard riche, `tools.allowed: string[]`) est une **cible doc / T-V3-RG-1 non câblée**. En P0 :

- soit on le remplace / scinde par un schéma « catalogue d'agents métier » aligné sur le bundle ;
- soit on le laisse comme aspiration et on versionne un schéma `specialist-catalog` réellement signé.

Ne pas prétendre que le schéma enterprise actuel est le contrat runtime.

### Refs d'outils (stable)

Ne **pas** signer le nom runtime desktop `managed__ihora__list_users` (convention sidecar). Signer :

```yaml
tools:
  allowed:
    - connector_id: ihora
      tool: list_users
    - connector_id: ihora
      tool: get_timesheet
  forbidden:
    - connector_id: ihora
      tool: create_timesheet   # write réel du catalogue ihora
```

Le desktop résout vers `managed__{connector_id}__{tool}` à l'enregistrement (double underscore, comme le code actuel).

Les **domaines** (`rh.read`, etc.) : hors contrat P0 ; presets UX admin éventuels en P4 (expansés en refs atomiques à la publication).

### Exemple d'agent métier (illustratif)

```yaml
specialists:
  - id: org.rh
    name: Agent RH
    # champs UI hérités personas : role, description, avatar_*
    doctrine:
      mission: ...
      principles: [...]
    output_contract:
      format: markdown
      required_sections: [...]
    tools:
      allowed:
        - { connector_id: ihora, tool: list_users }
        - { connector_id: ihora, tool: get_timesheet }
        - { connector_id: ihora, tool: list_absences }
      forbidden: []
    modes:
      regard: { tool_filter: pure_read }
      operative: { tool_filter: allowlist }
```

Règles de publication :

- chaque ref ∈ `tools[]` d'un connecteur allowlisté org ;
- sinon refus ;
- dual-read desktop : bundles `personas[]` seuls → agents métier sans panel jusqu'à resync.

---

## 7. Console tenant (UX admin)

Évolution de `/adminspace/regards` (aujourd'hui JSON brut, create + publish, pas d'edit) :

- liste versionnée (draft → publish → revoke) ;
- fiche agent métier : identité, doctrine, output contract, modes, champs UI (avatar, …) ;
- **picker d'outils** : arbre connecteur → `tools[]`, filtré par allowlist org ; badges `read` / `write` ;
- nouvelle version plutôt qu'édition opaque in-place ;
- overrides user sur connecteurs orthogonaux (deny → `degraded_tools` desktop).

**Décision retenue :** édition des agents d'entreprise **uniquement** en console cloud. Desktop = consommation. Sets personnels locaux = hors gouvernance tenant (hors scope).

---

## 8. Sync et UI Workproba

```text
Publish org
  → SignedBundle { catalog_id, version, personas? , specialists?, signature, … }
  → GET /catalogs/regards
  → ManagedAgentsPort.install / activate (code actuel : ManagedRegardsPort ; étendu : lire specialists[])
  → refresh UI desktop
```

Endpoint device : **garder** `GET /catalogs/regards` (pas de rename bloquant). Alias `/specialists` non requis en P0–P1.

Après sync (manuel CloudPanel / `sync_managed_regards` d'abord ; auto en P4) :

| Surface | Comportement |
|---|---|
| Liste agents métier | Catalogue org (noms, avatars, provenance **Administré** / `managed`) |
| Fiche détail | Panel d'outils **affiché** (read vs write) |
| Solliciter un regard | Mode read-only ; exécution tools read **à partir de P2** |
| Assistant | Délégation bornée **à partir de P3** ; retrait dump parent en **P4** |
| Hub Capacités | Inventaire connecteurs inchangé sémantiquement |
| Dégradé | Tool au panel mais hors snapshot / deny / off → indicateur |

---

## 9. Phasage

Pas d'exécution d'outils Regard avant le runner.

### P0 — Admin tenant + contrat (débloquant) · **livré** (06/08/2026)

- [x] Schéma catalogue réellement signé + signer : `specialists[]` (`specialist-catalog.schema.json` ; tools `{connector_id, tool}`).
- [x] Dual-read `personas[]` (cloud signer + desktop `SignedBundle` / port `ManagedRegardsPort`).
- [x] Éditeur admin + picker tools (create-only ; escape hatch JSON ; pas d'edit brouillon).
- [x] Validation publish vs allowlist org (allowed = allowlist+exists ; forbidden = exists).
- [x] `regard-enterprise.schema.json` = doc/archive (README schemas).
- [x] Tests : signature, refus ref invalide, dual-read, clés test bloquées en prod.
- Hors P0 reporté : édition brouillon existant ; champs avatar/`output_contract` dans le form (via JSON avancé).

### P1 — Sync + UI Workproba (affichage) · **livré** (06/08/2026)

- [x] Pull → liste / fiche ; **afficher** le panel.
- [x] Libellés Agent métier / Regard (i18n FR/EN + fiche agent).
- [x] Pas d'exécution tools Regard ; dump `managed__*` parent inchangé.

### P2 — Runtime Regard (lecture) · **livré** (06/08/2026)

- [x] `SpecialistRun` mode `regard` + `ToolAllowlistResolver` (`specialist_run.py`, `tool_allowlist.py`).
- [x] Brancher UI ask + `ask_personas` sur ce runner (tools `effect: read` only).
- [x] Tests : lecture ; impossibilité write enregistré ; `degraded_tools` ; legacy personas.

### P3 — Runtime opératoire + délégation · **livré** (06/08/2026)

- [x] Mode `operative` + HAG via invoke existant.
- [x] `summon_specialist(specialist_id, task, mode=regard|operative)` outil de délégation parent.
- [x] Parent peut encore exposer `managed__*` (transition ; retrait = P4).
- [x] Tests : write approval/deny ; id inconnu ; Regard read-only durci.

### P4 — Retrait dump parent + polish · **livré** (06/08/2026)

- [x] Retirer `register_managed_connector_tools` **et** `invoke_managed_connector` de l'agent **parent** (zéro contournement).
- [x] Managed tools accessibles via SpecialistRun (regard/operative) / `summon_specialist` uniquement.
- [x] Sync auto : manuel (`sync_managed_regards`) ; indicateurs dégradés partiels OK.
- [x] Meeting / croisés : pas de branchement tools (hors scope trivial).

### Post-P4 — Streaming handoff · **livré** (06/08/2026)

- [x] SpecialistRun via `agent.iter` ; events SSE parent scopés (`parent_tool_call_id`).
- [x] Handoff compact (détail replié) ; ordre encart puis texte Imp post-délégation.
- [x] HAG nested (carte confirmation orpheline) ; normalisation thinking Mistral non-stream.
- [x] Tests : `test_specialist_run`, `test_mistral_stream`, handoff / `useChatStream` / `activityGroup`.

**Ordre :** P0 → P1 → P2 → P3 → P4 → polish streaming.

---

## 10. Modules / fichiers probables

**Cloud**

- `api/schemas/` (nouveau schéma catalogue ou refactor `regard-enterprise.schema.json`)
- `api/src/core/signatures/regard-bundle.signer.ts` (+ tests)
- `regards.service.ts`, `catalogs.service.ts`
- Front admin : `RegardsPage` / éditeur, tools depuis config connectors

**Desktop AI**

- `workproba_personas/` (orchestrator → `SpecialistRun`, tools agent)
- `plugins/ports/managed_regards.py` (`SignedBundle`, install/activate)
- `workproba_cloud/plugin.py` (enregistrement tools pour un run ; sync)
- `capabilities_turn.py` (freeze connecteurs inchangé)
- `invoke_managed_connector_impl` = unique write path

**Front desktop**

- `usePersonas.ts`, side chat / panneau central, CloudPanel, i18n

---

## 11. Non-objectifs (ce plan)

- Exécution de l'agent dans le cloud / `agent-gateway`.
- MCP comme bus d'outils produit.
- Édition des agents d'entreprise depuis le desktop.
- Remplacer le hub Capacités par la liste des agents métier.
- Toucher au modèle projet partagé / sync artefacts (hors sujet).

---

## 12. Garde-fous

1. Un seul chemin d'invoke write (pas de bypass HAG).  
2. Regard = aucun tool write enregistré.  
3. Intersection runtime §3 obligatoire.  
4. Après P4 : ni `managed__*` plat ni `invoke_managed_connector` sur le parent.  
5. Dual-read `personas[]` / `specialists[]`.  
6. Ids agents métier = registry only (fail-closed).  
7. Revue catalogue : `effect: read` mensonger = risque processus.  
8. Panel signé = tools managed seulement (pas les tools locaux du sidecar).

---

## 13. Risques

| Risque | Mitigation |
|---|---|
| Break signature / clients old | dual-read ; tests signer cloud + verify desktop |
| Ref `managed__*` dans le bundle | refs `{connector_id, tool}` (§6) |
| Confusion schéma enterprise string[] vs refs objets | P0 tranche le schéma réellement signé |
| Tool `read` avec side-effect | revue catalogue |
| Latence | peu d'itérations Regard ; timeout ; croisés lecture en parallèle |
| Contournement via `invoke_managed_connector` | retiré du parent en P4 |
| Capacité regards off alors que sync OK | prérequis §3 ; UI honnête |
| Deux outils agent (`ask` vs `summon`) | P3 : un contrat de délégation |

---

## 14. Décisions

### Retenues

1. Édition agents d'entreprise = console cloud uniquement.  
2. Allowlist P0 = tool atomique `{connector_id, tool}`.  
3. Catalogue versionné = **N agents métier** (`specialists[]` ; évolution possible `agents[]`).  
4. Refresh : manuel d'abord, auto en P4.  
5. Sets personnels locaux hors gouvernance tenant.  
6. Endpoint device : garder `GET /catalogs/regards`.  
7. Après P4 : **zéro** managed plat / fallback invoke sur le parent.  
8. Panel signé = managed cloud only ; mémoire locale optionnelle en Regard comme aujourd'hui.  
9. P3 : un outil de délégation (`summon_specialist`) ; `ask_personas` aligné ou déprécié vers ce contrat.

### Encore ouvertes (mineures)

1. Remplacer vs archiver `regard-enterprise.schema.json` en P0.  
2. Meeting : rester texte ou brancher le runner Regard (reporté P4+).  
3. Nom i18n exact des boutons (« Solliciter le regard » vs « Demander un avis »).

---

## 15. Synthèse

> Chaque tenant administre ses agents métier (paramètres + panel d'outils managed) dans Improba Cloud, à partir des connecteurs qu'il a autorisés. Workproba enrollé tire le catalogue signé et met à jour listes, fiches, regards et délégation. En cible, l'assistant ne voit plus le catalogue `managed__*` en vrac : il mobilise des agents métier bornés. Le Regard est le mode read-only du même objet.

Prochaine étape : smoke E2E (sync → Regard → summon operative → HAG) ; édition brouillon admin ; sync auto optionnelle. Le streaming handoff (détail replié, ordre encart / texte Imp) est **livré**.
