"""Runner sandbox pour l'outil `run_code`.

Exécute du code Python généré par le LLM dans un environnement isolé et borné :

- **Répertoire de travail jetable** : chaque exécution tourne dans un tmpdir
  dédié ; les fichiers projet demandés (`project_files`) y sont *copiés* (et non
  bind-mountés depuis le vrai projet), donc le code généré ne peut ni lire ni
  écrire en dehors de ce qu'on lui expose.
- **Environnement minimal** : seules quelques variables sûres (PATH, HOME,
  TMPDIR, LANG) sont transmises ; les secrets du sidecar (clés LLM, secret
  interne) ne fuient jamais vers le code exécuté.
- **Limites POSIX** (RLIMIT_CPU / AS / FSIZE / NOFILE / CORE) appliquées via
  `preexec_fn`, plus un nouveau groupe de processus pour pouvoir tuer tout le
  tree en cas de timeout.
- **Isolation réseau best-effort** : si `bubblewrap` (`bwrap`) est disponible sur
  Linux et `sandbox_block_network` est activé, on wrapping l'exécution dans un
  namespace réseau séparé (`--unshare-net`) + FS en lecture seule. Sinon, on
  retombe sur les limites ressources seules (avec avertissement journalisé).
- **Sortie bornée** : stdout/stderr sont lus en flux et tronqués à
  `sandbox_output_max_bytes` pour éviter la bombe mémoire (`communicate()`
  bufferise tout sinon).
- **Fichiers générés** : les fichiers créés dans le tmpdir (hors ceux copiés)
  sont collectés et renvoyés dans `SandboxResult.files`.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.limits import DEFAULT_LIMITS, Limits
from app.schemas import GeneratedFile, SandboxResult

logger = logging.getLogger(__name__)

# Environnement minimal transmis au code exécuté. On exclut volontairement tout
# ce qui pourrait contenir un secret (clés API, INTERNAL_SECRET, etc.).
_SAFE_ENV_KEYS = ("PATH", "LANG", "LC_ALL", "LC_CTYPE")
_HOME_SUBDIR = "home"


@lru_cache(maxsize=1)
def _bwrap_available() -> bool:
    """Sonde `bubblewrap` avec exactement les flags utilisés en production.

    bwrap peut être installé mais inutilisable sans capability
    (`--unshare-net` requiert CAP_SYS_ADMIN ou un userns activé). On exécute une
    sonde réelle (cachée) pour décider du profil d'isolation.
    """
    if os.name != "posix" or not sys.platform.startswith("linux"):
        return False
    bwrap = shutil.which("bwrap")
    if not bwrap:
        return False
    with tempfile.TemporaryDirectory(prefix="wp-bwrap-probe-") as probe_dir:
        try:
            proc = subprocess.run(
                [
                    bwrap,
                    "--die-with-parent",
                    "--unshare-net",
                    "--unshare-uts",
                    "--new-session",
                    "--ro-bind-try", "/", "/",
                    "--dev", "/dev",
                    "--proc", "/proc",
                    "--tmpfs", "/tmp",
                    "--tmpfs", "/run",
                    "--bind", probe_dir, "/work",
                    "--chdir", "/work",
                    "--",
                    sys.executable,
                    "-I",
                    "-c",
                    "pass",
                ],
                timeout=8,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, OSError):
            return False
    return proc.returncode == 0


@dataclass(frozen=True)
class SandboxRunner:
    timeout_seconds: int
    limits: Limits = field(default=DEFAULT_LIMITS)

    async def run(
        self,
        *,
        code: str,
        project_files: list[str],
        project_root: str | Path | None = None,
    ) -> SandboxResult:
        root = Path(project_root).expanduser().resolve() if project_root else None
        if root is not None and not root.is_dir():
            return SandboxResult(stderr=f"Dossier projet invalide : {root}")

        work_dir = Path(tempfile.mkdtemp(prefix="wp-sandbox-"))
        copied: set[str] = set()
        try:
            copy_warnings = self._expose_project_files(
                work_dir=work_dir, project_root=root, project_files=project_files, copied=copied
            )

            argv, cwd, env, preexec = self._build_command(work_dir)
            result = await self._execute(
                argv=argv, cwd=cwd, env=env, preexec=preexec, work_dir=work_dir, code=code
            )
            files = self._collect_generated_files(work_dir=work_dir, copied=copied)

            metadata: dict[str, Any] = {
                **(result.metadata or {}),
                "runtime": "subprocess",
                "isolation": self._isolation_profile(),
                "project_files_requested": len(project_files),
                "project_files_copied": len(copied),
            }
            if copy_warnings:
                metadata["copy_warnings"] = copy_warnings
            return SandboxResult(
                stdout=result.stdout,
                stderr=result.stderr,
                files=files,
                timed_out=result.timed_out,
                metadata=metadata,
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    # --- construction de la commande ---------------------------------------

    def _build_command(
        self, work_dir: Path
    ) -> tuple[list[str], Path, dict[str, str], Any]:
        env = self._build_env(work_dir)
        preexec = self._preexec_fn() if os.name == "posix" else None

        use_bwrap = self.limits.sandbox_block_network and _bwrap_available()
        if use_bwrap:
            bwrap = shutil.which("bwrap")
            assert bwrap is not None  # couvert par _bwrap_available()
            argv = self._bwrap_argv(bwrap, work_dir)
            return argv, work_dir, env, preexec

        if self.limits.sandbox_block_network:
            logger.warning(
                "bubblewrap (bwrap) indisponible ou sans permissions : isolation "
                "réseau désactivée. Le code exécuté garde un accès réseau. Le "
                "reste (tmpdir jetable, env minimal, limites POSIX) reste actif."
            )
        return [sys.executable, "-I", "-c", self._placeholder_code()], work_dir, env, preexec

    def _bwrap_argv(self, bwrap: str, work_dir: Path) -> list[str]:
        # Namespace réseau séparé (pas de réseau), FS racine en lecture seule,
        # /work en lecture-écriture (tmpdir jetable). --die-with-parent évite
        # les zombies si le sidecar meurt.
        return [
            bwrap,
            "--die-with-parent",
            "--unshare-net",
            "--unshare-uts",
            "--new-session",
            "--ro-bind-try", "/", "/",
            "--dev", "/dev",
            "--proc", "/proc",
            "--tmpfs", "/tmp",
            "--tmpfs", "/run",
            "--bind", str(work_dir), "/work",
            "--chdir", "/work",
            "--",
            sys.executable,
            "-I",
            "-c",
            self._placeholder_code(),
        ]

    def _placeholder_code(self) -> str:
        # Le vrai code est passé via stdin pour éviter qu'il apparaisse dans la
        # ligne de commande (visible via `ps`) et pour supporter des scripts
        # volumineux sans se heurter à ARG_MAX. Voir `_feed_stdin`.
        return "import sys; exec(sys.stdin.read())"

    def _build_env(self, work_dir: Path) -> dict[str, str]:
        # HOME pointe vers un sous-dossier du tmpdir (créé) pour que les libs qui
        # écrivent dans ~/.cache (matplotlib, etc.) restent contenues dans la
        # sandbox au lieu de tomber sur un HOME inexistant.
        home_dir = work_dir / _HOME_SUBDIR
        home_dir.mkdir(parents=True, exist_ok=True)

        env: dict[str, str] = {}
        for key in _SAFE_ENV_KEYS:
            value = os.environ.get(key)
            if value:
                env[key] = value
        env["HOME"] = str(home_dir)
        env["TMPDIR"] = str(work_dir / "tmp")
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONHASHSEED"] = "0"
        env["MPLBACKEND"] = "Agg"  # pas de GUI matplotlib dans la sandbox
        return env

    def _isolation_profile(self) -> str:
        if self.limits.sandbox_block_network and _bwrap_available():
            return "bwrap"
        return "resource-limits" if os.name == "posix" else "none"

    # --- limites POSIX (exécuté dans l'enfant avant exec) ------------------

    def _preexec_fn(self) -> Any:
        limits = self.limits

        def _setup() -> None:
            import signal
            try:
                import resource
            except ImportError:  # improbable sur POSIX
                return

            def setrlimit(res: int, soft: int, hard: int) -> None:
                try:
                    resource.setrlimit(res, (soft, hard))
                except (ValueError, OSError):
                    pass

            setrlimit(resource.RLIMIT_CPU, limits.sandbox_cpu_seconds, limits.sandbox_cpu_seconds)
            mem_bytes = limits.sandbox_memory_mb * 1024 * 1024
            setrlimit(resource.RLIMIT_AS, mem_bytes, mem_bytes)
            fsize = limits.sandbox_file_size_mb * 1024 * 1024
            setrlimit(resource.RLIMIT_FSIZE, fsize, fsize)
            # 1024 : assez pour les libs type numpy/pandas, tout en empêchant la
            # bombe à FDs. Ne pas descendre à 256 (casserait bwrap au setup).
            setrlimit(resource.RLIMIT_NOFILE, 1024, 1024)
            setrlimit(resource.RLIMIT_CORE, 0, 0)

            # Groupe de processus dédié pour pouvoir tuer tout le tree.
            try:
                os.setpgid(0, 0)
            except OSError:
                pass
            # Ignorer SIGINT pendant l'init de l'enfant.
            try:
                signal.signal(signal.SIGINT, signal.SIG_DFL)
            except OSError:
                pass

        return _setup

    # --- exécution + lecture bornée ----------------------------------------

    async def _execute(
        self,
        *,
        argv: list[str],
        cwd: Path,
        env: dict[str, str],
        preexec: Any,
        work_dir: Path,
        code: str,
    ) -> SandboxResult:
        tmp_dir = work_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            env=env,
            preexec_fn=preexec,
        )

        assert process.stdin is not None
        assert process.stdout is not None
        assert process.stderr is not None
        # Le code est passé via stdin (voir _placeholder_code).
        stdin_task = asyncio.create_task(self._feed_stdin(process.stdin, code))

        max_out = self.limits.sandbox_output_max_bytes
        stdout_task = asyncio.create_task(self._read_capped(process.stdout, max_out))
        stderr_task = asyncio.create_task(self._read_capped(process.stderr, max_out))

        # On attend uniquement la fin du process sous timeout ; les tâches de
        # lecture tournent indépendamment (elles ne doivent pas être annulées
        # par wait_for, sinon on perd les tampons déjà lus).
        try:
            await asyncio.wait_for(process.wait(), timeout=self.timeout_seconds)
        except TimeoutError:
            self._kill_tree(process)
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                pass
            stdin_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await stdin_task
            out_bytes, out_truncated = await stdout_task
            err_bytes, err_truncated = await stderr_task
            return SandboxResult(
                stderr="Exécution interrompue (timeout)."
                + (" Sortie tronquée." if err_truncated else ""),
                timed_out=True,
                metadata={
                    "exit_code": process.returncode if process.returncode is not None else -1,
                    "stdout_truncated": out_truncated,
                    "stderr_truncated": err_truncated,
                },
            )

        try:
            await stdin_task
        except (BrokenPipeError, ConnectionResetError, asyncio.CancelledError):
            pass
        out_bytes, out_truncated = await stdout_task
        err_bytes, err_truncated = await stderr_task
        exit_code = process.returncode if process.returncode is not None else -1
        return self._build_result(
            stdout=out_bytes,
            stderr=err_bytes,
            exit_code=exit_code,
            out_truncated=out_truncated,
            err_truncated=err_truncated,
        )

    async def _feed_stdin(self, stdin: asyncio.StreamWriter, code: str) -> None:
        # Le vrai code utilisateur est injecté ici (pas dans argv).
        try:
            stdin.write(code.encode("utf-8"))
            await stdin.drain()
            stdin.close()
            await stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass

    async def _read_capped(self, stream: asyncio.StreamReader, max_bytes: int) -> tuple[bytes, bool]:
        out = bytearray()
        truncated = False
        while True:
            chunk = await stream.read(65536)
            if not chunk:
                break
            if not truncated:
                room = max_bytes - len(out)
                if room > 0:
                    out.extend(chunk[:room])
                if len(out) >= max_bytes:
                    truncated = True
            # on continue à drainer pour ne pas bloquer le child sur un pipe plein
        return bytes(out), truncated

    def _build_result(
        self,
        *,
        stdout: bytes,
        stderr: bytes,
        exit_code: int,
        out_truncated: bool,
        err_truncated: bool,
    ) -> SandboxResult:
        return SandboxResult(
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            metadata={
                "exit_code": exit_code,
                "stdout_truncated": out_truncated,
                "stderr_truncated": err_truncated,
            },
        )

    def _kill_tree(self, process: asyncio.subprocess.Process) -> None:
        try:
            process.kill()
        except ProcessLookupError:
            return
        if os.name == "posix":
            try:
                import signal as _signal

                os.killpg(os.getpgid(process.pid), _signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass

    # --- fichiers projet / générés -----------------------------------------

    def _expose_project_files(
        self,
        *,
        work_dir: Path,
        project_root: Path | None,
        project_files: list[str],
        copied: set[str],
    ) -> list[str]:
        warnings: list[str] = []
        if not project_files:
            return warnings
        if project_root is None:
            warnings.append("project_files ignorés : aucun project_root fourni.")
            return warnings

        max_size = self.limits.sandbox_file_size_mb * 1024 * 1024
        for raw in project_files:
            try:
                src = Path(raw).expanduser()
                if not src.is_absolute():
                    src = project_root / raw
                src = src.resolve()
                if not src.is_relative_to(project_root):
                    warnings.append(f"Fichier hors projet ignoré : {raw}")
                    continue
                if not src.is_file():
                    warnings.append(f"Fichier introuvable : {raw}")
                    continue
                if src.stat().st_size > max_size:
                    warnings.append(f"Fichier trop volumineux ignoré : {raw}")
                    continue
                dest = work_dir / src.relative_to(project_root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                copied.add(src.relative_to(project_root).as_posix())
            except OSError as exc:
                warnings.append(f"Erreur copie {raw}: {exc}")
        return warnings

    def _collect_generated_files(self, *, work_dir: Path, copied: set[str]) -> list[GeneratedFile]:
        files: list[GeneratedFile] = []
        max_files = self.limits.sandbox_max_output_files
        max_file_bytes = self.limits.sandbox_max_output_file_bytes
        for path in sorted(work_dir.rglob("*")):
            if len(files) >= max_files:
                break
            if not path.is_file():
                continue
            rel = path.relative_to(work_dir).as_posix()
            if rel in copied or rel.startswith("tmp/") or rel.startswith("home/"):
                continue
            size = path.stat().st_size
            content_b64: str | None = None
            if size <= max_file_bytes:
                content_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            files.append(
                GeneratedFile(
                    path=rel,
                    metadata={"size_bytes": size, "truncated": content_b64 is None},
                    content_base64=content_b64,
                )
            )
        return files
