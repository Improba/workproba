# Installer Workproba

Guide d'installation pour **Windows**, **macOS** et **Linux**. Ce document s'adresse aux utilisateurs finaux (pas aux développeurs).

## Introduction

Workproba V2 s'installe via un **installateur** adapté à votre système :

| Système | Fichiers proposés |
|---|---|
| Windows | `.msi` ou `.exe` (installateur NSIS) |
| macOS | `.dmg` |
| Linux | `.deb` ou `.AppImage` |

En V2, ces installateurs ne sont **pas signés numériquement**. La signature officielle (certificats Windows, notarisation Apple, etc.) est prévue pour la V3.

**Conséquence normale :** au premier lancement, Windows ou macOS affiche un **avertissement de sécurité**. Ce n'est pas un signe que le fichier est corrompu. Cela signifie seulement que l'éditeur n'a pas encore de certificat reconnu par l'OS.

> Téléchargez Workproba **uniquement depuis la source officielle Improba** (page de release GitHub de l'équipe, ou lien fourni par votre service informatique). Un fichier obtenu ailleurs peut être dangereux.

Le moteur d'intelligence artificielle est **embarqué** dans l'installateur : vous n'avez pas à installer Python, Node.js ou d'autres outils de développement.

---

## Où télécharger

Les installateurs sont publiés sur la **page Releases** du dépôt Workproba, lors du dépôt d'une version taguée `v*` (par exemple `v0.2.0`).

Choisissez le fichier correspondant à votre système :

- **Windows (64 bits)** : `Workproba_*_x64-setup.exe` (NSIS) ou `Workproba_*_x64_*.msi`
- **macOS Apple Silicon (M1, M2, …)** : `Workproba_*_aarch64.dmg`
- **macOS Intel** : `Workproba_*_x64.dmg`
- **Linux Debian/Ubuntu (64 bits)** : `workproba_*_amd64.deb`
- **Linux (toute distribution, 64 bits)** : `workproba_*_amd64.AppImage`

---

## Windows

### Installation

1. Téléchargez le fichier `.msi` ou `.exe`.
2. Double-cliquez pour lancer l'installateur.
3. Suivez les étapes à l'écran (langue française ou anglaise selon l'installateur).

### Avertissement SmartScreen

Windows peut afficher :

> **Windows a protégé votre ordinateur**  
> Microsoft Defender SmartScreen a empêché le démarrage d'une application non reconnue.

**Ce qu'il faut faire :**

1. Cliquez sur **« Informations complémentaires »** (ou « More info »).
2. Cliquez sur **« Exécuter quand même »** (ou « Run anyway »).

**Pourquoi cet écran apparaît :** en V2, Workproba n'est pas signé avec un certificat Authenticode reconnu par Microsoft. SmartScreen bloque par défaut les applications sans réputation établie. Si vous avez téléchargé le fichier depuis la source officielle Improba, vous pouvez continuer en toute confiance.

### Premier lancement

L'application apparaît dans le menu Démarrer sous le nom **Workproba**. Au premier démarrage, l'assistant vous demande votre nom et votre organisation.

---

## macOS

### Installation

1. Téléchargez le fichier `.dmg` adapté à votre Mac (Apple Silicon ou Intel).
2. Ouvrez le `.dmg` (double-clic).
3. Glissez **Workproba** dans le dossier **Applications**.
4. Éjectez le disque image.

### Avertissement Gatekeeper

Au premier lancement, macOS peut afficher :

> **« Workproba » ne peut pas être ouvert car il provient d'un développeur non identifié.**

**Méthode 1 (recommandée, sans ligne de commande) :**

1. Ouvrez **Réglages Système** (ou Préférences Système sur les versions plus anciennes).
2. Allez dans **Confidentialité et sécurité** (ou **Sécurité**).
3. Vous devriez voir un message concernant Workproba. Cliquez sur **« Ouvrir quand même »**.
4. Relancez Workproba depuis le dossier Applications.

**Méthode 2 (ligne de commande, pour un administrateur ou un collègue technique) :**

Ouvrez le Terminal et exécutez :

```bash
xattr -dr com.apple.quarantine /Applications/Workproba.app
```

Cette commande retire l'attribut de quarantaine posé par macOS sur les fichiers téléchargés depuis Internet.

**Pourquoi cet écran apparaît :** en V2, Workproba n'est pas signé avec un certificat **Developer ID** ni notarisé par Apple. Gatekeeper bloque les applications non signées par défaut.

### Version macOS minimale

Workproba requiert **macOS 10.13** (High Sierra) ou plus récent.

---

## Linux

Deux formats sont disponibles. Choisissez celui qui convient à votre distribution.

### Option A : paquet `.deb` (Debian, Ubuntu, dérivés)

1. Téléchargez `workproba_*_amd64.deb`.
2. Installez-le :

```bash
sudo dpkg -i workproba_*.deb
```

3. Si des dépendances manquent (notamment les bibliothèques WebKit), corrigez l'installation :

```bash
sudo apt-get install -f
```

4. Lancez **Workproba** depuis le menu des applications ou en tapant `workproba` dans un terminal.

Le paquet `.deb` installe Workproba comme une application système classique (raccourci, désinstallation via le gestionnaire de paquets).

### Option B : fichier `.AppImage` (toute distribution)

1. Téléchargez `workproba_*_amd64.AppImage`.
2. Rendez-le exécutable et lancez-le :

```bash
chmod +x workproba_*.AppImage
./workproba_*.AppImage
```

L'AppImage ne s'installe pas dans le système : c'est un fichier unique que vous pouvez placer où vous voulez (Bureau, dossier personnel, clé USB). Aucun avertissement de signature ne s'applique en général sur Linux.

### Dépendances Linux

Le paquet `.deb` déclare automatiquement ses dépendances (`libwebkit2gtk`, indicateur de barre des tâches). L'AppImage embarque la plupart des bibliothèques nécessaires.

---

## Vérifier l'intégrité du fichier (optionnel)

Chaque release officielle peut fournir une **empreinte SHA256** (checksum) à côté des installateurs sur la page Releases.

Pour vérifier un fichier téléchargé :

**Windows (PowerShell) :**

```powershell
Get-FileHash -Algorithm SHA256 .\Workproba_*.msi
```

**macOS / Linux :**

```bash
shasum -a 256 workproba_*.deb
# ou
sha256sum workproba_*.AppImage
```

Comparez le résultat avec la valeur SHA256 publiée sur la release. Si les deux correspondent, le fichier n'a pas été altéré pendant le téléchargement.

---

## Désinstaller Workproba

| Système | Procédure |
|---|---|
| **Windows** | **Paramètres** > **Applications** > **Applications installées**, cherchez **Workproba**, puis **Désinstaller**. Vous pouvez aussi utiliser **Ajouter ou supprimer des programmes** dans le Panneau de configuration. |
| **macOS** | Ouvrez le dossier **Applications**, glissez **Workproba** vers la Corbeille, puis videz la Corbeille. |
| **Linux (.deb)** | `sudo apt remove workproba` |
| **Linux (.AppImage)** | Supprimez simplement le fichier `.AppImage`. Aucune trace ne reste dans le système. |

### Données personnelles après désinstallation

Workproba stocke vos données localement (conversations, mémoire, paramètres) dans un dossier applicatif sur votre machine. La désinstallation de l'application **ne supprime pas automatiquement** ces données.

Si vous souhaitez tout effacer, demandez à votre service informatique ou consultez la documentation sur le stockage local (`docs/workspace-storage.md`, section technique).

---

## Prochaines étapes (V3)

La V3 prévoit de lever les avertissements au premier lancement :

| Système | Amélioration prévue |
|---|---|
| Windows | Signature Authenticode (certificat éditeur) |
| macOS | Signature Developer ID + notarisation Apple |
| Linux | Signature des paquets (selon la stratégie de distribution retenue) |

En attendant, les installateurs V2 restent fonctionnels et sûrs **si téléchargés depuis la source officielle**.

---

## Souveraineté et confidentialité

Après installation, Workproba fonctionne **entièrement en local** sur votre ordinateur :

- **Pas de télémétrie** : l'application n'envoie pas de données d'usage à Improba.
- **Pas de compte obligatoire** : vous pouvez travailler sans créer de compte en ligne.
- **Vos documents restent sur votre disque** : l'assistant lit et modifie les fichiers de votre dossier projet, pas sur un serveur distant.
- **Cloud optionnel** : la synchronisation cloud (plugin expérimental en V2) n'est activée que si vous ou votre administrateur l'activez explicitement.

Votre service informatique peut verrouiller certains paramètres (langue, plugins autorisés, accès réseau) via un **preset enterprise**. Dans ce cas, un bandeau « Mode verrouillé » s'affiche dans l'application.

---

## Besoin d'aide ?

- **Problème d'installation** : contactez votre service informatique ou la personne qui vous a fourni le lien de téléchargement.
- **Avertissement SmartScreen ou Gatekeeper** : c'est attendu en V2. Suivez les étapes de ce guide.
- **Questions sur l'utilisation** : consultez [intention.md](./intention.md) pour comprendre le fonctionnement général de Workproba.
