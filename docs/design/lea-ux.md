# Workproba, proposition UX

Auteur : Léa (UX strategist), débat avec Inès (lead designer).

## 1. Architecture de l'information et hiérarchie

### Choix : une seule sidebar à gauche, à deux niveaux, pas deux panneaux.

Structure de la sidebar, de haut en bas :

1. **En-tête de sidebar** : le workspace actif (icône dossier + nom), cliquable, ouvre un **switcher de workspaces récents** (menu transient, pas un panneau permanent). Bouton "Ouvrir un dossier" en pied de ce menu.
2. **Section "Conversations"** du workspace actif : liste scrollable, groupée par date (Aujourd'hui / Cette semaine / Plus ancien), comme Claude/Cursor. Bouton "Nouvelle conversation" en haut de la section.
3. **Pied de sidebar** : statut compact (sidecar IA connecté, mémoire RAG indexée), réduit à une ligne.

Le centre reste **la conversation**. La droite reste **l'arborescence fichiers** du workspace.

### Pourquoi pas deux panneaux séparés (workspaces | conversations) ?

Pour un non-codeur, jongler entre deux listes demande de savoir "où je suis dans la hiérarchie". Cursor peut se le permettre : sa cible vit dans un éditeur 8 h/jour. Nous non. Un seul panneau qui **change de niveau sémantique** avec un retour clair (le nom du workspace en haut), c'est moins de surfaces à scanner, une seule colonne à lire. Le switcher de workspaces est un **menu** (transient), pas un panneau permanent : on l'ouvre, on choisit, il disparaît. Le workspace actif reste le repère stable.

### Pourquoi ne pas tout mettre dans un seul arbre (workspace > conversations) ?

Les workspaces sont des **dossiers physiques** (peu, ~5 à 20 max), les conversations sont des **objets nombreux** (des dizaines par workspace). Mélanger les deux crée une profondeur injustifiée et masque les conversations sous un nœud replié. On sépare : workspaces = switcher plat, conversations = liste dédiée.

Modèle mental : *un dossier de chantier (workspace), plusieurs discussions (conversations) dedans.*

## 2. Parcours clés

### 2.1 Premier lancement (aucun workspace)

- Fenêtre centrée, fond de marque Improba, **grande zone d'action unique** : "Ouvrez un dossier pour commencer".
- Sous-titre court : "Workproba travaille sur vos fichiers locaux. Rien ne sort de votre machine sauf ce que vous envoyez à l'IA."
- Un seul bouton principal : "Choisir un dossier" (sélecteur natif Tauri).
- Pas de liste récente vide affichée : on n'affiche jamais un état vide "il n'y a rien", on affiche l'action.
- À droite : arbre vide avec un pictogramme et la phrase "Votre arborescence apparaîtra ici."

### 2.2 Ouvrir un nouveau dossier

1. User clique "Choisir un dossier" (onboarding) ou le bouton dans le switcher de workspaces.
2. Sélecteur natif Tauri. L'user valide un dossier.
3. Retour frontend : on génère un UUID, on crée `~/.local/share/fr.improba.workproba/workspaces/{uuid}/`, on indexe l'arborescence (Rust, watch_FS démarré).
4. Feedback transitoire : "Dossier 'Devis 2026' ouvert" (toast 2 s).
5. **Première conversation créée automatiquement**, titrée "Nouvelle conversation", focus dans la zone de saisie. Micro-onboarding inline dans le premier message assistant : "Je suis prêt. Décrivez ce que vous voulez faire avec les fichiers de ce dossier."
6. L'arborescence de droite se peuple.

### 2.3 Basculer entre workspaces récents

1. User clique le **workspace actif en tête de sidebar**.
2. Menu transient : liste des workspaces récents (icône + nom + chemin tronqué), item actif surligné, entrée "Ouvrir un autre dossier…".
3. Clic sur un item : fermeture du menu, chargement du workspace, conversations rechargées, arbre de droite rafraîchi. La conversation active du workspace est restaurée (la dernière ouverte, ou la première si jamais visité).
4. Pas de confirmation : changement de contexte réversible.

### 2.4 Démarrer une nouvelle conversation dans le workspace courant

1. Bouton "Nouvelle conversation" en haut de la section conversations (et raccourci `Cmd/Ctrl+N`, affiché en tooltip, pas exigé).
2. La conversation courante est **mise en pause** (état scroll + messages persisté en mémoire et sur disque).
3. Une nouvelle conversation vide prend le centre, titre provisoire "Nouvelle conversation", focus dans la saisie.
4. Le titre se renomme automatiquement après le premier échange user/assistant (résumé court côté IA), comme Claude. L'user peut le renommer au double-clic.

### 2.5 Reprise d'une conversation existante

1. Clic sur une conversation dans la liste.
2. Chargement depuis le disque (Tauri). Pendant le chargement (<200 ms) : on garde la conversation précédente affichée avec un voile léger, pas un écran blanc.
3. Restauration de la **position de scroll** et de la sélection de message. On persiste `scrollTop` + `activeMessageId` dans les métadonnées de la conversation.
4. L'arbre de droite reste le même (c'est le workspace), mais on peut optionnellement **surligner les fichiers déjà touchés dans cette conversation** (toggle discret).

### 2.6 Interaction avec l'arborescence

- **Déplier/replier** : clic sur le chevron du nœud (pas sur le label, pour éviter l'ouverture accidentelle). `→`/`←` clavier pour expand/collapse.
- **Ouvrir dans l'OS** : double-clic sur le label = ouvrir le fichier avec l'application par défaut du système (Tauri `open`). Action la plus "non-codeur" : on ne veut pas un éditeur de code intégré, on veut "ouvrir mon devis.docx dans Word".
- **Révéler dans le Finder/Explorer** : menu contextuel (clic droit) + bouton "Révéler" sur le nœud survolé.
- **Filtrer** : barre de filtre en tête de l'arbre (toujours visible). Filtre flou, instantané, avec affichage du chemin parent en filigrane pour désambiguïser.
- **Raccourcis clavier** : `Cmd/Ctrl+P` ouvre le filtre et focus direct. On n'exige pas les raccourcis, on les offre.

### 2.7 Pendant que l'agent travaille (streaming + tool calls)

Moment le plus anxiogène pour un non-codeur. Le soulagement est le critère numéro un.

- **Centre** : le message assistant se construit en streaming, curseur de frappe doux. Au-dessus du bloc, un statut animé : "L'agent réfléchit…" puis "L'agent lit `devis.pdf`…" puis "L'agent modifie `facture.xlsx`…" (libellés humains, pas `tool_call:read_file`).
- **Droite (arbre)** : les fichiers **touchés pendant la session** reçoivent un badge discret (un point coloré Improba pour "créé/modifié récemment"). Le nœud se déplie automatiquement pour être visible, et un surlignage temporaire (fade out sur 3 s) signale le changement. Pas de clignotement, pas de saut de scroll violent.
- **Sidebar** : la conversation active affiche un point d'activité à côté de son titre.
- **Pied de sidebar** : le statut sidecar passe de "Connecté" à "Travaille…" avec un pulse subtil.
- L'user peut **arrêter** (bouton "Arrêter" remplace "Envoyer" pendant le streaming). Arrêter toujours visible et accessible.

## 3. États et feedback

### États vides (jamais "vide", toujours "action")

- **Aucun workspace** : écran d'accueil décrit en 2.1.
- **Workspace ouvert, aucune conversation** : impossible par design (on crée la première conversation à l'ouverture). On élimine un état vide.
- **Dossier workspace vide** (aucun fichier) : arbre de droite affiche "Ce dossier est vide. Glissez-y des fichiers ou demandez à l'agent d'en créer." Avec un bouton "Créer un premier fichier". On transforme le vide en invitation.

### Chargements

- Changement de workspace : voile léger sur le précédent (pas d'écran blanc).
- Indexation initiale de l'arbre (gros dossier) : barre fine en pied de l'arbre, "Indexation de 12 480 fichiers…", disparaît à la fin. Jamais de spinner plein écran.

### Erreurs

- **Sidecar IA injoignable** : bannière discrète en pied de la conversation (pas en plein écran), "L'agent est injoignable pour le moment. Nouvelle tentative dans 3 s…" avec bouton "Réessayer maintenant". La zone de saisie reste active. On ne bloque jamais la saisie.
- **Fichier supprimé entre deux opérations** : toast non bloquant "Le fichier n'existe plus" + l'arbre se met à jour via le watch.
- **Permission dossier refusée** : message clair, "Workproba n'a pas accès à ce dossier", avec un lien vers la doc courte.

### Streaming

- Indicateur "L'agent réfléchit…" avant le premier token (et non un message vide qui s'affiche puis se remplit). Distinguer "réflexion" (rien encore) et "rédaction" (tokens arrivents), ça rassure.

## 4. Arborescence droite, "nickel et performante"

### Modèle de données (côté front)

Un arbre en mémoire, plat par profondeur, indexé par chemin absolu :

```ts
type TreeNode = {
  path: string // absolu, clé unique
  name: string
  isDir: boolean
  depth: number
  children?: string[] // chemins enfants, chargés lazy
  loaded: boolean // enfants déjà fetchés ?
  sessionState: 'idle' | 'created' | 'modified' // pendant la session
}
```

Un `Map<string, TreeNode>` + un tableau de chemins visibles (correspond aux nœuds dépliés), servi à la virtualisation.

### Virtualisation

vue-virtual-scroller déjà dispo : on ne rend que les nœuds visibles + marge. Pour 50 000 fichiers, défilement fluide. Hauteur de ligne fixe (26 px), profondeur rendue par padding gauche calculé, pas par DOM imbriqué (gain de perf et de simplicité de scroll).

### Mise à jour temps réel

- Côté Rust : un watcher filesystem par workspace (`notify`). On émet des événements Tauri typés : `fs:create`, `fs:modify`, `fs:delete`, `fs:rename`.
- Côté front : un store Pinia consomme les événements, met à jour le `Map`, et ne re-rend que la branche concernée (les ancêtres du chemin touché). Pas de re-indexation globale.
- **Debounce** : on groupe les rafales (un `git checkout` qui touche 500 fichiers ne doit pas faire 500 mises à jour UI). Fenêtre de 150 ms, puis une seule passe de réconciliation.
- **Tri stable** : dossiers d'abord, puis fichiers, alphabétique insensible à la casse. Option "Fichiers modifiés récemment en haut" dans un menu de préférences de l'arbre (offerte, pas par défaut).

### Lazy expand

Les enfants d'un dossier ne sont jamais chargés tant que le nœud n'est pas déplié. À l'ouverture du workspace, on ne charge que **le premier niveau** + les éventuels dossiers précédemment dépliés (persistés dans les métadonnées du workspace). Pour un dossier à 10 000 entrées, on pagine le rendu des enfants par le virtualizer, pas de pagination logicielle visible.

### Recherche/filtre instantané

- Saisie dans la barre de filtre : filtre flou sur le nom, affichage des résultats à plat avec chemin parent en filigrane gris. Échappement du mode filtre par `Esc`, retour à l'arbre déplié.
- Pendant le filtre, les nœuds matchés se déplient automatiquement, leurs ancêtres aussi.
- Compteur : "12 résultats".

### Accessibilité clavier

- L'arbre est une `tree` ARIA avec `treeitem`. Navigation `↑/↓`, expand/collapse `→/←`, ouverture `Entrée`, révéler `Cmd/Ctrl+R` (offert).
- Focus visible : anneau de focus Improba, jamais supprimé.

### Indicateurs de session

- `created` : badge vert "nouveau".
- `modified` : badge orange "modifié".
- Réinitialisés au changement de conversation (option : "Garder le surlignage entre les conversations" en préférences).

## 5. Marque et repérage "je suis dans Workproba"

Sans surcharger, trois points de repère :

1. **Titre de fenêtre natif** : "Workproba, {nom du workspace}". Le premier mot = la marque, toujours là dans la barre des tâches OS. Gratuit et puissant.
2. **Logo compact en tête de sidebar** : un logotype Improba mini (pas une grosse bannière), accolé au nom du workspace actif. C'est le repère "je suis dans la bonne app".
3. **Accent couleur** : une seule couleur d'accent Improba, utilisée pour le focus, les badges de session, le statut "travaille", le bouton principal d'envoi. Une seule. Jamais éparpillée.

Micro-élément de marque : la signature de l'assistant dans les messages (avatar petit format + prénom), qui crée une présence humaine cohérente avec la marque. On n'est pas un outil froid, on est un atelier avec quelqu'un dedans.

## 6. Risques UX et arbitrages

- **Densité vs respiration** : arbre de fichiers dense (24 px) maximise l'information mais peut impressionner un non-codeur. Compromis proposé : 26 px. Décision design (Inès).
- **Arbre persistant vs masquable** : pour les petits écrans (13"), l'arbre droit peut encombrer. Panneau **repliable** avec mémorisation de l'état par workspace, raccourci `Cmd/Ctrl+B` (offert, non exigé). La sidebar gauche ne se masque pas : c'est le repère stable.
- **Raccourcis clavier pour non-codeurs** : les proposer sans les exiger. Tous les boutons primaires visibles et labellisés. Palette de commandes `Cmd/Ctrl+K` ? Puissant mais potentiellement effrayant. Avis : oui, avec libellés en clair ("Nouvelle conversation", pas "chat.new"), ça devient une aide à la découverte plutôt qu'un repaire d'experts.
- **Renommage automatique des conversations** : pratique mais peut déstabiliser. Undo de renommage discret.
- **Surlignage des fichiers touchés pendant le travail de l'IA** : dépliage auto + fade out. À valider sur un vrai dossier de test.

## 7. Arbitrages à soumettre à Inès

1. **Sidebar unique à deux niveaux (mon choix) vs deux panneaux workspaces/conversations** : valider le modèle "switcher transient + liste conversations dédiée", ou tester les deux en maquette rapide avec 3 non-codeurs ?
2. **Badge de session dans l'arbre (vert "nouveau" / orange "modifié")** : on garde les deux niveaux, ou on simplifie à un seul signal "touché pendant la session" pour réduire la charge visuelle ?
3. **Palette de commandes `Cmd/Ctrl+K`** : on l'offre comme aide à la découverte (libellés en clair), ou on la réserve à une phase 2 pour ne pas surcharger le premier lancement ?
