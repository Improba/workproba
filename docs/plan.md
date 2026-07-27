# Plan : Spécialistes, Regards et config par tenant

> **Statut :** plan d'intention / architecture (pas d'implémentation)  
> **Date :** 27/07/2026 (revues solo ×2)  
> **Décideur :** Syl  
> **Liens :** [intention.md](./intention.md) · [intention Improba](../../workproba-improba/intention.md) (amendement 27/07) · [glossaire](../../workproba-improba/roadmaps/glossaire.md) · [positionnement cloud / regards](../../workproba-improba/roadmaps/positionnement-cloud-regards.md) · [architecture cloud](../../workproba-improba/roadmaps/architecture-cloud.md) · [capacites.md](./capacites.md) · [plugins.md](./plugins.md)

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
User ↔ Assistant (chat principal)
         ├─ mobilise des Spécialistes (panels d'outils selon profil)
         └─ User peut solliciter le regard d'un Spécialiste
               = même spécialiste, mode lecture / avis
```

| Concept | Rôle | Outils |
|---|---|---|
| **Assistant** (Imp) | Face à l'utilisateur ; orchestre | fichiers, mémoire, délégation |
| **Spécialiste** | Profil métier (RH, juridique, …) avec panel d'outils | lecture, et éventuellement écriture selon profil |
| **Regard** | Mode consultatif d'un spécialiste (UI ou via l'assistant) | **read-only** : consulter, expliquer, recommander |

Principes :

- Spécialiste = sous-agent borné (doctrine + allowlist + contrat de sortie), pas un second chatbot généraliste ;
- capacités cloud = **inventaire** ; le spécialiste **sélectionne et discipline** un sous-ensemble ;
- pas « 1 app cloud = 1 spécialiste » ;
- regards croisés = plusieurs spécialistes en mode Regard ;
- écritures : spécialiste opératoire et/ou assistant + Human Approval Gate ; **jamais** via le bouton Regard ;
- code interne peut rester `personas` ; UI produit : Spécialiste / Regard.

---

## 3. Source de vérité : config par tenant

Le tenant (organisation) configure ses spécialistes. Workproba desktop **consomme** et met l'UI à jour.

| Acteur | Où | Quoi |
|---|---|---|
| **Org admin** | Console Improba Cloud (`/adminspace`) | Spécialistes : doctrine / consignes, contrat de sortie, **panel d'outils** |
| **Org admin** | `/adminspace/connectors` (déjà là) | Inventaire : quels connecteurs l'org autorise |
| **User desktop** | Workproba | Reçoit le catalogue org, voit, mobilise (regard / assistant). Ne définit pas les spécialistes d'entreprise. |

```text
Tenant (org)
  1. Allowlist connecteurs (existant, fail-closed si vide)
  2. Définit Spécialiste RH :
       - paramètres (nom, doctrine, format, modes regard / opératoire)
       - outils cochés parmi tools[] des connecteurs autorisés
  3. Publie une version signée

Poste Workproba (enrollé)
  ← pull catalogue (sync regards)
  → capacité locale « Regards » / plugin personas active (sinon catalogue non mobilisable)
  → UI spécialistes / regards se met à jour
  → runtime n'expose que le panel au SpecialistRun
```

Prérequis desktop : compte cloud connecté **et** capacité / plugin regards active. La sync catalogue ne remplace pas l'activation de la capacité.

### Deux couches à ne pas fusionner

1. **Inventaire org** (existant) : quels connecteurs existent pour cette org.  
2. **Profil spécialiste** (à ajouter) : pour *ce* spécialiste, quels tools + quelle doctrine.

Hub Capacités ≠ liste des spécialistes : capacités = tuyaux ; spécialistes = profils métier paramétrés par le tenant.

### Couches d'autorisation effectives

**À la publication (cloud) :** chaque ref `{connector_id, tool}` doit exister dans le `tools[]` d'un connecteur **allowlisté pour l'org**. Sinon refus.

**Au runtime (desktop),** un tool managed n'est enregistré / appelable par un `SpecialistRun` que s'il passe :

1. connecteur dans le snapshot de tour (`managed_allowed_connector_ids` : déjà le résultat de allowlist org ∩ overrides user ∩ wanted espace ∩ enable local ∩ entitlements cloud plugin) ;
2. tool présent dans le panel du spécialiste (allowed − forbidden) ;
3. filtre de mode (Regard → uniquement tools du cache avec `effect: read`) ;
4. filtre `visibility` selon `ui_mode` (guided / standard / advanced), comme aujourd'hui pour `managed__*`.

La couche org n'est pas re-vérifiée ad hoc dans le runner : elle est déjà matérialisée dans `GET /connectors` + construction du snapshot. Le publish admin évite les panels incohérents en amont.

---

## 4. État actuel (faits)

| Domaine | Existe | Manque |
|---|---|---|
| Personas / Regards desktop | avis LLM **sans outils managed**, UI SSE (`ask` / meeting / discuss), mémoire projet optionnelle, sets locaux + catalogues signés (`personas[]`) | panel d'outils managed, doctrine structurée consommée |
| Managed tools | cache, snapshot tour, noms `managed__{connector}__{tool}`, HAG sauf `effect: read`, fallback `invoke_managed_connector` | exposition progressive, allowlist par profil |
| Cloud connectors | allowlist org + overrides user, `GET /connectors` avec `tools[]` (`effect`, `visibility`, `input_schema`) | lien vers spécialistes |
| Cloud regards | draft / publish / revoke ; payload peu validé ; `SignedBundle` | signer n'embarque que `personas[]` ; admin = JSON brut ; pas de picker tools |
| Schéma `regard-enterprise.schema.json` | `doctrine`, `tools.allowed/forbidden` en **string[]** (outils « locaux » type search_kb), `output_contract` au niveau **d'un** regard | non branché au signer/runtime ; format string[] **incompatible** avec les refs managed ciblées ; pas de `specialists[]` |
| Lien regards ↔ tools | aucun | allowlist par spécialiste |
| Desktop SignedBundle | dataclass avec `personas` obligatoire | champ `specialists` à ajouter (dual-read) |

Surfaces utiles :

- Desktop : `workproba_personas/`, `workproba_cloud/plugin.py` (`sync_managed_regards`), `capabilities_turn.py`, `ManagedRegardsPort`, `POST /plugins/cloud/sync-regards`, CloudPanel
- Cloud : `/adminspace/regards`, `/adminspace/connectors`, `GET /catalogs/regards`, `regard-bundle.signer.ts`

Outils agent personas actuels : `ask_personas`, `simulate_meeting` (pas de `summon_*`).

---

## 5. Architecture cible

```text
workproba-cloud (par org)
  connectors[]     → inventaire tools (effect, visibility, input_schema)
  specialists[]    → profils dans le bundle signé (doctrine + allowlist + output_contract)
       │
       ▼ pull / sync (DeviceBearer)
Desktop
  ManagedRegardsPort (étendu) + cache connectors
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

1. **SpecialistRegistry** : sets locaux + catalogues managés enrichis (évolution de la résolution personas / `ManagedRegardsPort`)  
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

**Décision retenue (ferme) :** un catalogue versionné = **N spécialistes** via `specialists[]` dans payload + bundle ; dual-read `personas[]` pour les vieux clients / bundles.

Le schéma `regard-enterprise.schema.json` (un document = un regard riche, `tools.allowed: string[]`) est une **cible doc / T-V3-RG-1 non câblée**. En P0 :

- soit on le remplace / scinde par un schéma « catalogue de spécialistes » aligné sur le bundle ;
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

### Exemple de spécialiste (illustratif)

```yaml
specialists:
  - id: org.rh
    name: Spécialiste RH
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
- dual-read desktop : bundles `personas[]` seuls → spécialistes sans panel jusqu'à resync.

---

## 7. Console tenant (UX admin)

Évolution de `/adminspace/regards` (aujourd'hui JSON brut, create + publish, pas d'edit) :

- liste versionnée (draft → publish → revoke) ;
- fiche spécialiste : identité, doctrine, output contract, modes, champs UI (avatar, …) ;
- **picker d'outils** : arbre connecteur → `tools[]`, filtré par allowlist org ; badges `read` / `write` ;
- nouvelle version plutôt qu'édition opaque in-place ;
- overrides user sur connecteurs orthogonaux (deny → `degraded_tools` desktop).

**Décision retenue :** édition des spécialistes d'entreprise **uniquement** en console cloud. Desktop = consommation. Sets personnels locaux = hors gouvernance tenant (hors scope).

---

## 8. Sync et UI Workproba

```text
Publish org
  → SignedBundle { catalog_id, version, personas? , specialists?, signature, … }
  → GET /catalogs/regards
  → ManagedRegardsPort.install / activate (étendu : lire specialists[])
  → refresh UI desktop
```

Endpoint device : **garder** `GET /catalogs/regards` (pas de rename bloquant). Alias `/specialists` non requis en P0–P1.

Après sync (manuel CloudPanel / `sync_managed_regards` d'abord ; auto en P4) :

| Surface | Comportement |
|---|---|
| Liste spécialistes | Catalogue org (noms, avatars, provenance **Administré** / `managed`) |
| Fiche détail | Panel d'outils **affiché** (read vs write) |
| Solliciter un regard | Mode read-only ; exécution tools read **à partir de P2** |
| Assistant | Délégation bornée **à partir de P3** ; retrait dump parent en **P4** |
| Hub Capacités | Inventaire connecteurs inchangé sémantiquement |
| Dégradé | Tool au panel mais hors snapshot / deny / off → indicateur |

---

## 9. Phasage

Pas d'exécution d'outils Regard avant le runner.

### P0 — Admin tenant + contrat (débloquant)

- Schéma catalogue réellement signé + signer : `specialists[]` (doctrine, tools `{connector_id, tool}`, output_contract, modes, champs UI).
- Dual-read `personas[]` (cloud signer + desktop `SignedBundle` / `ManagedRegardsPort`).
- Éditeur admin + picker tools.
- Validation publish vs allowlist org.
- Clarifier le sort du schéma `regard-enterprise.schema.json` (remplacé, scindé, ou doc only).
- Tests : org A / org B ; signature ; refus ref invalide.

### P1 — Sync + UI Workproba (affichage)

- Pull → liste / fiche ; **afficher** le panel.
- Libellés Spécialiste / Regard (i18n + glossaire).
- Pas d'exécution tools Regard ; dump `managed__*` parent inchangé.

### P2 — Runtime Regard (lecture)

- `SpecialistRun` mode `regard` + `ToolAllowlistResolver`.
- Brancher UI ask + chemin regard de `ask_personas` sur ce runner (tools `effect: read` only).
- Tests : lecture timesheet / absences ; impossibilité d'enregistrer un write ; `degraded_tools`.

### P3 — Runtime opératoire + délégation

- Mode `operative` + HAG via invoke existant.
- `summon_specialist(specialist_id, task, mode=regard|operative)` comme **outil unique de délégation** ; `ask_personas` devient un thin wrapper ou est déprécié vers ce contrat (éviter deux sémantiques).
- Parent peut encore exposer `managed__*` (transition).
- Tests : write approval / deny ; TOCTOU enable local.

### P4 — Retrait dump parent + polish

- Retirer `register_managed_connector_tools` **et** `invoke_managed_connector` de l'agent **parent** (zéro contournement).
- Sync auto ; indicateurs dégradés ; presets domaines admin optionnels.
- Meeting / croisés : brancher sur runner Regard si on veut des tools en lecture ; sinon laisser texte.

**Ordre :** P0 → P1 → P2 → P3 → P4.

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
- Édition des spécialistes d'entreprise depuis le desktop.
- Remplacer le hub Capacités par la liste des spécialistes.
- Toucher au modèle projet partagé / sync artefacts (hors sujet).

---

## 12. Garde-fous

1. Un seul chemin d'invoke write (pas de bypass HAG).  
2. Regard = aucun tool write enregistré.  
3. Intersection runtime §3 obligatoire.  
4. Après P4 : ni `managed__*` plat ni `invoke_managed_connector` sur le parent.  
5. Dual-read `personas[]` / `specialists[]`.  
6. Ids spécialistes = registry only (fail-closed).  
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

1. Édition spécialistes d'entreprise = console cloud uniquement.  
2. Allowlist P0 = tool atomique `{connector_id, tool}`.  
3. Catalogue versionné = **N spécialistes** (`specialists[]`).  
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

> Chaque tenant administre ses Spécialistes (paramètres + panel d'outils managed) dans Improba Cloud, à partir des connecteurs qu'il a autorisés. Workproba enrollé tire le catalogue signé et met à jour listes, fiches, regards et délégation. En cible, l'assistant ne voit plus le catalogue `managed__*` en vrac : il mobilise des spécialistes bornés. Le Regard est le mode read-only du même objet.

Prochaine étape : ticket **P0** (schéma catalogue signé + signer + éditeur admin + validation allowlist + dual-read desktop + fixture multi-org).
