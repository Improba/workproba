# Design system Workproba

Document de convergence, synthèse du débat entre **Inès** (lead designer) et **Léa** (UX strategist). Voir `lea-ux.md` pour la proposition UX détaillée et les parcours.

Ce document est la source de vérité pour l'implémentation UI.

## 0. Décisions d'arbitrage (convergence)

| # | Arbitrage | Décision | Raison |
|---|---|---|---|
| 1 | Sidebar unique à deux niveaux vs deux panneaux | **Sidebar unique** (switcher transient de workspaces + liste conversations dédiée) | Moins de surfaces à scanner pour un non-codeur ; repère stable = workspace actif en tête |
| 2 | Badge de session arbre (vert "nouveau" / orange "modifié") | **Simplifié à un signal unique** : un point cyan "touché pendant la session", tooltip donne le détail (créé/modifié) | Réduit la charge visuelle ; le détail reste accessible au survol |
| 3 | Palette de commandes `Cmd/Ctrl+K` | **Phase 2** (pas au premier lancement) | Garder le premier lancement sobre ; on l'ajoutera comme aide à la découverte |
| 4 | Hauteur de ligne arbre | **26 px** | Compromis densité/respiration pour non-codeurs |
| 5 | Sidebar gauche masquable | **Non** (repliable en rail 56px d'icônes, jamais totalement cachée) | C'est le repère stable (Léa) |
| 6 | Panneau fichiers droit | **Repliable** (`Cmd/Ctrl+B`), état mémorisé par workspace | Petit écrans 13" |

## 1. Palette (tokens Anubis)

L'identité Improba sert d'**accent et de branding**, pas de fond de chat. Le chat se lit en mode clair sobre. Bleu canard `#203D52` = branding + états actifs ; cyan `#3ECFD9` = accent d'action / focus / "travaille" ; or `#FFCC49` et violet `#B077DD` = signaux secondaires (RAG, badges).

### Mode clair (défaut)

```scss
// Fond & surfaces
--bg:            #F6F7F9;  // fond app, derrière les panneaux
--surface:       #FFFFFF;  // panneaux, cartes, sidebar
--surface-2:     #F0F2F5;  // hover, zones imbriquées
--surface-3:     #E6EAEE;  // pressé, diviseurs épais

// Texte
--text:          #1C2A36;  // principal (canard très foncé, lisible)
--text-muted:    #5B6B7B;  // secondaire, meta, chemins
--text-faint:    #8A99A8;  // filigrane, placeholders

// Bordures
--border:        #E4E8ED;
--border-strong: #D2D9E0;

// Marque & accents
--primary:       #203D52;  // bleu canard : header actif, workspace actif, lien
--primary-soft:  #E8EEF2;  // fond actif workspace (canard très dilué)
--accent:        #2BB5C2;  // cyan action (contraste AA sur blanc)
--accent-strong: #3ECFD9;  // cyan plein : hover, streaming
--accent-soft:   #DCF6F7;  // fond focus / badge session

--gold:          #E0A93A;  // or AA sur blanc : "modifié"
--gold-soft:     #FFF3D6;
--violet:        #9A63C7;  // violet AA sur blanc : RAG, "créé"
--violet-soft:   #F0E4FA;

// Sémantique
--success:       #2E9E74;
--danger:        #D64545;
--danger-soft:   #FBE6E6;
--warning:       var(--gold);

// Neutres Anubis (échelle) -> mapper sur surface/text ci-dessus
--neutral-lowest:  #FFFFFF;
--neutral-lower:   #F6F7F9;
--neutral-low:     #F0F2F5;
--neutral-medium:  #C6CFD8;
--neutral-high:    #8A99A8;
--neutral-higher:  #5B6B7B;
--neutral-highest: #1C2A36;
```

### Mode sombre

```scss
--bg:            #131F28;  // canard très foncé, pas noir pur
--surface:       #1B2C38;
--surface-2:     #23384A;
--surface-3:     #2C4254;
--text:          #E8EEF2;
--text-muted:    #9FB0C0;
--text-faint:    #6E8195;
--border:        #2C4254;
--border-strong: #3A5266;
--primary:       #3ECFD9;  // cyan devient primaire en sombre (plus lisible)
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

## 2. Typographie

- **UI / titres / body** : `Varela Round` (charger la webfont ; fallback `Inter`, `system-ui`, `sans-serif`). Varela Round n'a que 400 ; on simule le "700" via `font-weight: 700` avec fallback `Inter` 700 pour les titres car Varela Round n'a pas de bold natif. Alternative : `Quicksand` (bold available, même esprit arrondi) pour les titres. **Décision** : body en Varela Round 400, titres en `Quicksand` 600/700 (arrondi, graspable, a un vrai bold). Fallbacks `Varela Round, system-ui`.
- **Code / diff / chemins** : `JetBrains Mono`, fallback `ui-monospace, SFMono-Regular, Menlo, monospace`.

Échelle :

| Rôle | Taille | Weight | Police |
|---|---|---|---|
| display (onboarding) | 2rem / 32px | 700 | Quicksand |
| h1 (titre workspace) | 1.4rem / 22px | 700 | Quicksand |
| h2 | 1.15rem / 18px | 700 | Quicksand |
| h3 (section sidebar) | 0.8125rem / 13px | 700, uppercase, letter-spacing 0.06em | Quicksand |
| body (chat) | 0.9375rem / 15px | 400 | Varela Round, line-height 1.6 |
| meta (dates, chemins) | 0.8125rem / 13px | 500 | Varela Round |
| code | 0.85rem / 13.6px | 400 | JetBrains Mono |

Rayons : `--r-sm: 8px`, `--r-md: 12px`, `--r-lg: 16px`, `--r-pill: 999px`. Ombres douces : `--shadow-1: 0 1px 2px rgba(28,42,54,0.06)`, `--shadow-2: 0 6px 24px rgba(28,42,54,0.10)`.

## 3. Mise en page 3 colonnes

```
+---------------------------------------------------------------+
| Title bar Tauri (40px) : [logo Workproba]  ·  {workspace}  ·  [theme] |
+----------+--------------------------------------+--------------+
| Sidebar  |              Centre                  |   Fichiers   |
| 268px    |  (chat, max-width 760px centré)      |   320px      |
| rail 56  |                                      |   repliable  |
| repliable|                                      |   Cmd/Ctrl+B |
+----------+--------------------------------------+--------------+
```

- **Sidebar gauche** : 268px (min 240, max 320). Repliable en rail d'icônes 56px (jamais totalement cachée). Contient, de haut en bas : en-tête workspace actif + switcher transient ; section "Conversations" (nouvelle conversation + liste groupée par date) ; pied statut sidecar.
- **Centre** : fluide, `min-width 480px`. Surface de chat centrée, `max-width 760px`, marges généreuses (48px latéraux desktop). Zone de saisie ancrée en bas, `max-width 760px` alignée au chat.
- **Fichiers droite** : 320px (min 240, max 400). Repliable, état mémorisé par workspace. Barre de filtre en tête, arbre virtualisé dessous, pied = barre d'indexation (si gros dossier).
- **États vides** : voir `lea-ux.md` §3 (toujours une action, jamais un "vide").

Responsive webview desktop : sous 1100px, le panneau fichiers se replie automatiquement (raccourci pour le rouvrir). Sous 820px, la sidebar passe en rail 56px.

## 4. Composants clés (à créer/styliser sur Quasar)

### 4.1 `WorkprobaTitleBar` (barre de titre fenêtre, custom decoration Tauri)
40px, fond `--surface` + bordure basse `--border`. Gauche : logotype "Workproba" en Quicksand 700, couleur `--primary` (clair) / `--accent` (sombre). Centre : nom du workspace + chemin tronqué, `--text-muted`. Droite : toggle thème + boutons fenêtre (reduce/min/close via Tauri `window` API). Zone de drag fenêtre (`data-tauri-drag-region`).

### 4.2 `WorkspaceSidebar` (gauche)
- **En-tête workspace actif** : carte `--surface-2`, rayon `--r-md`, padding 10px 12px. Icône dossier (Lucide `folder`, couleur `--accent`), nom (Quicksand 700, 1 line ellipsis), chemin tronqué (meta, `--text-faint`). Chevron `chevron-down` indique "cliquez pour switcher". Au clic : menu transient (`q-menu`) listant les workspaces récents (icône + nom + chemin tronqué), item actif surligné `--accent-soft` + liseré gauche `--accent`, et une entrée `+ Ouvrir un autre dossier…`.
- **Section Conversations** : titre h3 "CONVERSATIONS" + bouton icône "Nouvelle conversation" (`message-square-plus`) à droite. Liste scrollable, groupée par date (labels h3 "Aujourd'hui", "Cette semaine", "Plus ancien"). Item : padding 8px 10px, rayon `--r-sm`, titre 1 line ellipsis, date meta en dessous. Hover `--surface-2`. Actif `--accent-soft` + texte `--text` + liseré gauche 3px `--accent`. Pendant le streaming : point cyan pulsant à gauche du titre.
- **Pied statut** : 1 ligne, icône point (cyan connecté / gris idle / cyan pulse "travaille"), libellé meta.

### 4.3 `ChatSurface` (centre)
Reprise de `front/src/components/chat/` existant, restylé : bulles pleine largeur (pas de bulles flottantes, façon Claude), avatar assistant petit format (sigle "W" Improba sur pastille `--accent-soft`), messages user alignés avec fond `--surface-2` rayon `--r-lg`. Cartes tool-calls repliables style "fichier lu" / "fichier modifié" (libellés humains de Léa). Sources RAG : pastilles violet `--violet`. Zone de saisie : textarea auto-extensible, rayon `--r-lg`, bordure `--border`, focus `--accent`. Bouton "Envoyer" primaire `--accent`, devient "Arrêter" (icône `square`) pendant le streaming. Statut streaming au-dessus du message : "L'agent réfléchit…" / "L'agent lit `x`…".

### 4.4 `FileExplorer` (droite)
- **Barre de filtre** : input avec icône `search` (Lucide), placeholder "Filtrer les fichiers…", `Cmd/Ctrl+P` focus. Toujours visible.
- **Arbre virtualisé** : `vue-virtual-scroller` `RecycleScroller`, hauteur de ligne **26px**, profondeur par padding gauche `depth * 16px` (pas de DOM imbriqué). Dossiers d'abord, puis fichiers, tri insensible à la casse. Icônes Lucide par type (`folder`, `file-text`, `file-code`, `file-image`, `file-spreadsheet`, `file-pdf`…). Chevron `chevron-right`/`chevron-down` sur les dossiers (clic = expand/collapse, pas sur le label).
- **Point de session** : pastille cyan `--accent` 6px à droite du nœud si touché pendant la session (signal unique, tooltip "créé" / "modifié"). Dépliage auto + surlignage `--accent-soft` fade-out 3s.
- **Actions** : double-clic label = ouvrir dans l'OS (Tauri `open`). Clic droit = menu "Révéler dans le Finder/Explorer", "Ouvrir". Bouton "Révéler" au survol.
- **ARIA** : `role="tree"`, `treeitem`, navigation clavier `↑/↓/→/←/Entrée`.
- **Pied indexation** : barre fine + libellé "Indexation de N fichiers…" pendant l'index init.

### 4.5 Micro-interactions (respiration Improba)
- Transitions : `transition: 180ms cubic-bezier(0.4, 0, 0.2, 1)` sur hover/active.
- "Souffle" : le statut "travaille" pulse `opacity 0.6 → 1` sur 1.6s ease-in-out.
- Apparition message assistant : fade + translateY 4px sur 220ms.
- Dépliage arbre : rotation chevron 150ms, slide-down enfants 180ms.
- Pas de clignotement, pas de saut. Tout est doux.

## 5. Touche d'âme Improba

- **Formes arrondies généreuses** (`--r-lg` 16px sur cartes et saisie, `--r-pill` sur badges/statuts).
- **Cyan = souffle** : l'unique couleur qui "respire" (pulse streaming, focus, point de session). Le reste est neutre. Une seule couleur vive, jamais éparpillée.
- **Respiration** : margins latéraux 48px, paddings généreux, line-height 1.6, beaucoup d'air blanc.
- **Logotype mini** en barre de titre + sigle "W" assistant : repère de marque discret mais constant.
- **Titre fenêtre natif** : "Workproba — {workspace}" (premier mot = marque dans la barre des tâches OS).

## 6. Plan d'implémentation

1. **Tokens design** : `front/src/css/workproba-tokens.scss` (variables light/dark) + import global. Chargement webfonts Varela Round + Quicksand + JetBrains Mono.
2. **Layout 3 colonnes** : `front/src/layouts/WorkprobaLayout.vue` (remplace `StandardLayout` pour la cible desktop) + `WorkprobaTitleBar.vue`.
3. **Sidebar gauche** : `WorkspaceSidebar.vue` + `WorkspaceSwitcher.vue` + `ConversationList.vue` (branché sur `workspaceSession` + `useProject`).
4. **Centre chat** : rebrancher `ChatView` existant dans le nouveau layout + restyle.
5. **FileExplorer droite** : `FileExplorer.vue` + `useFileTree` (store) + watcher Rust (`desktop/src-tauri/src/commands/fs_watch.rs`, crate `notify`).
6. **États vides & onboarding** : écran premier lancement, états arbre vide / sidecar injoignable.

Le watcher FS Rust (étape 5) est le morceau le plus technique : nouveau module Rust + événements Tauri + store front + debounce 150ms + réconciliation partielle.
