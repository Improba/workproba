# Install Workproba

Installation guide for **Windows**, **macOS**, and **Linux**. This document is for end users (not developers).

## Introduction

Workproba installs via an **installer** suited to your system:

| System | Files offered |
|---|---|
| Windows | `.msi` or `.exe` (NSIS installer) |
| macOS | `.dmg` |
| Linux | `.deb` or `.AppImage` |

Installers are **not yet digitally signed**. Official signing (Windows certificates, Apple notarization, etc.) is planned for a future release.

**Expected consequence:** on first launch, Windows or macOS shows a **security warning**. This is not a sign that the file is corrupted. It only means the publisher does not yet have a certificate recognized by the OS.

> Download Workproba **only from the official Improba source** (the team's GitHub release page, or a link provided by your IT department). A file obtained elsewhere may be unsafe.

The artificial intelligence engine is **bundled** in the installer: you do not need to install Python, Node.js, or other development tools.

---

## Where to download

Installers are published on the Workproba repository **Releases** page when a tagged version is published (for example `v0.2.0`).

Choose the file for your system:

- **Windows (64-bit)**: `Workproba_*_x64-setup.exe` (NSIS) or `Workproba_*_x64_*.msi`
- **macOS Apple Silicon (M1, M2, …)**: `Workproba_*_aarch64.dmg`
- **macOS Intel**: `Workproba_*_x64.dmg`
- **Linux Debian/Ubuntu (64-bit)**: `workproba_*_amd64.deb`
- **Linux (any distribution, 64-bit)**: `workproba_*_amd64.AppImage`

---

## Windows

### Installation

1. Download the `.msi` or `.exe` file.
2. Double-click to launch the installer.
3. Follow the on-screen steps (French or English depending on the installer).

### SmartScreen warning

Windows may show:

> **Windows protected your PC**  
> Microsoft Defender SmartScreen prevented an unrecognized app from starting.

**What to do:**

1. Click **"More info"**.
2. Click **"Run anyway"**.

**Why this screen appears:** Workproba is not yet signed with an Authenticode certificate recognized by Microsoft. SmartScreen blocks applications without established reputation by default. If you downloaded the file from the official Improba source, you can proceed with confidence.

### First launch

The app appears in the Start menu under **Workproba**. On first startup, the assistant asks for your name and organization.

---

## macOS

### Installation

1. Download the `.dmg` file for your Mac (Apple Silicon or Intel).
2. Open the `.dmg` (double-click).
3. Drag **Workproba** into the **Applications** folder.
4. Eject the disk image.

### Gatekeeper warning

On first launch, macOS may show:

> **"Workproba" can't be opened because it is from an unidentified developer.**

**Method 1 (recommended, no command line):**

1. Open **System Settings** (or System Preferences on older versions).
2. Go to **Privacy & Security** (or **Security**).
3. You should see a message about Workproba. Click **"Open Anyway"**.
4. Relaunch Workproba from the Applications folder.

**Method 2 (command line, for an administrator or technical colleague):**

Open Terminal and run:

```bash
xattr -dr com.apple.quarantine /Applications/Workproba.app
```

This command removes the quarantine attribute macOS places on files downloaded from the Internet.

**Why this screen appears:** Workproba is not yet signed with a **Developer ID** certificate nor notarized by Apple. Gatekeeper blocks unsigned applications by default.

### Minimum macOS version

Workproba requires **macOS 10.13** (High Sierra) or newer.

---

## Linux

Two formats are available. Choose the one that fits your distribution.

### Option A: `.deb` package (Debian, Ubuntu, derivatives)

1. Download `workproba_*_amd64.deb`.
2. Install it:

```bash
sudo dpkg -i workproba_*.deb
```

3. If dependencies are missing (especially WebKit libraries), fix the installation:

```bash
sudo apt-get install -f
```

4. Launch **Workproba** from the applications menu or by typing `workproba` in a terminal.

The `.deb` package installs Workproba like a standard system application (shortcut, uninstall via package manager).

### Option B: `.AppImage` file (any distribution)

1. Download `workproba_*_amd64.AppImage`.
2. Make it executable and run it:

```bash
chmod +x workproba_*.AppImage
./workproba_*.AppImage
```

The AppImage does not install into the system: it is a single file you can place anywhere (Desktop, home folder, USB drive). Signature warnings generally do not apply on Linux.

### Linux dependencies

The `.deb` package declares its dependencies automatically (`libwebkit2gtk`, taskbar indicator). The AppImage bundles most required libraries.

---

## Verify file integrity (optional)

Each official release may provide a **SHA256 fingerprint** (checksum) next to the installers on the Releases page.

To verify a downloaded file:

**Windows (PowerShell):**

```powershell
Get-FileHash -Algorithm SHA256 .\Workproba_*.msi
```

**macOS / Linux:**

```bash
shasum -a 256 workproba_*.deb
# or
sha256sum workproba_*.AppImage
```

Compare the result with the SHA256 value published on the release. If they match, the file was not altered during download.

---

## Uninstall Workproba

| System | Procedure |
|---|---|
| **Windows** | **Settings** > **Apps** > **Installed apps**, search for **Workproba**, then **Uninstall**. You can also use **Add or Remove Programs** in Control Panel. |
| **macOS** | Open the **Applications** folder, drag **Workproba** to the Trash, then empty the Trash. |
| **Linux (.deb)** | `sudo apt remove workproba` |
| **Linux (.AppImage)** | Simply delete the `.AppImage` file. No trace remains in the system. |

### Personal data after uninstall

Workproba stores your data locally (conversations, memory, settings) in an application folder on your machine. Uninstalling the application **does not automatically delete** this data.

If you want to erase everything, ask your IT department or consult the documentation on local storage (`docs/workspace-storage.md`, technical section).

---

## Planned improvements

Future releases plan to remove first-launch warnings:

| System | Planned improvement |
|---|---|
| Windows | Authenticode signing (publisher certificate) |
| macOS | Developer ID signing + Apple notarization |
| Linux | Package signing (depending on distribution strategy) |

Until then, installers remain functional and safe **if downloaded from the official source**.

---

## Sovereignty and privacy

After installation, Workproba runs **entirely locally** on your computer:

- **No telemetry**: the app does not send usage data to Improba.
- **No mandatory account**: you can work without creating an online account.
- **Your documents stay on your disk**: the assistant reads and modifies files in your project folder, not on a remote server.
- **Optional cloud**: cloud sync (experimental plugin) is enabled only if you or your administrator explicitly activates it.

Your IT department can lock certain settings (language, allowed plugins, network access) via an **enterprise preset**. In that case, a "Locked mode" banner appears in the application.

---

## Need help?

- **Installation problem**: contact your IT department or the person who gave you the download link.
- **SmartScreen or Gatekeeper warning**: this is expected. Follow the steps in this guide.
- **Usage questions**: see [intention.md](./intention.md) to understand how Workproba works in general.
