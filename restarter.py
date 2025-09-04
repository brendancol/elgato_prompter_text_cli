#!/usr/bin/env python3
"""
restart_app.py — Restart an application by name (macOS + Windows)

Usage:
  python3 restart_app.py safari
  python3 restart_app.py "visual studio code"
  python3 restart_app.py com.google.Chrome
  python3 restart_app.py chrome
"""

import os, sys, time, subprocess
from pathlib import Path
from typing import Optional, List

# -------------------------
# Shared helpers
# -------------------------

def run(cmd: list[str], check=True, capture=True) -> str:
    res = subprocess.run(cmd, check=check, capture_output=capture, text=True)
    return (res.stdout or "").strip()

def is_macos() -> bool:
    return sys.platform == "darwin"

def is_windows() -> bool:
    return sys.platform.startswith("win")

# -------------------------
# macOS implementation (unchanged from your version)
# -------------------------

SPOTLIGHT_QUERY_TEMPLATE = (
    'kMDItemKind == "Application" && '
    '(kMDItemDisplayName == "*{q}*" || kMDItemCFBundleIdentifier == "*{q}*")'
)

def mac_mdfind_app(search: str) -> Optional[Path]:
    query = SPOTLIGHT_QUERY_TEMPLATE.format(q=search)
    out = run(["mdfind", query], check=False)
    hits = [Path(p) for p in out.splitlines() if p.endswith(".app")]
    if not hits:
        return None
    s = search.lower()
    def score(p: Path):
        path_str = str(p)
        name = p.stem.lower()
        return (
            2 if (path_str.startswith("/Applications/") or path_str.startswith("/System/Applications/")) else 0,
            2 if name.startswith(s) else 0,
            1 if s in name else 0,
            -len(path_str),
        )
    hits.sort(key=score, reverse=True)
    return hits[0]

def mac_bundle_id_for(app_path: Path) -> str:
    return run(["mdls", "-name", "kMDItemCFBundleIdentifier", "-raw", str(app_path)])

def mac_count_running_procs(bundle_id: str) -> int:
    out = run([
        "osascript", "-e",
        f'tell application "System Events" to count (every process whose bundle identifier is "{bundle_id}")'
    ], check=False)
    try:
        return int(out)
    except (ValueError, TypeError):
        return 0

def mac_pids_for(bundle_id: str) -> List[int]:
    out = run([
        "osascript", "-e",
        f'tell application "System Events" to get the unix id of every process whose bundle identifier is "{bundle_id}"'
    ], check=False)
    if not out:
        return []
    return [int(x.strip()) for x in out.split(",") if x.strip().isdigit()]

def mac_quit_app(bundle_id: str, timeout_s: float = 20.0, force_after_timeout: bool = True):
    subprocess.run(["osascript", "-e", f'tell application id "{bundle_id}" to quit'], check=False)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if mac_count_running_procs(bundle_id) == 0:
            return
        time.sleep(0.3)
    if force_after_timeout:
        for pid in mac_pids_for(bundle_id):
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass

def mac_launch_app(bundle_id: str):
    subprocess.run(["open", "-b", bundle_id], check=True)
    subprocess.run(["osascript", "-e", f'tell application id "{bundle_id}" to activate'], check=False)

# -------------------------
# Windows implementation
# -------------------------

def ps_exe() -> List[str]:
    """Prefer Windows PowerShell, fall back to PowerShell 7 if needed."""
    for exe in ("powershell", "pwsh"):
        try:
            subprocess.run([exe, "-NoProfile", "-Command", "$PSVersionTable.PSVersion"], capture_output=True)
            return [exe, "-NoProfile", "-Command"]
        except FileNotFoundError:
            continue
    raise RuntimeError("PowerShell not found in PATH.")

def ps_run(script: str, arg: Optional[str] = None, check=True) -> str:
    """Run a PowerShell script; pass one arg via $args[0] to avoid quoting issues."""
    cmd = ps_exe() + [script] + ([arg] if arg is not None else [])
    res = subprocess.run(cmd, check=check, capture_output=True, text=True)
    return (res.stdout or "").strip()

def win_find_running_pids(search: str) -> List[int]:
    script = r'''
$search = $args[0]
$like = "*" + $search + "*"
(Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like $like -or $_.CommandLine -like $like } |
  Select-Object -ExpandProperty ProcessId) -join "`n"
'''
    out = ps_run(script, search, check=False)
    return [int(x) for x in out.splitlines() if x.strip().isdigit()]

def win_exec_path_for_pid(pid: int) -> Optional[str]:
    script = r'''
$pid = [int]$args[0]
try {
  (Get-CimInstance Win32_Process -Filter "ProcessId = $pid").ExecutablePath
} catch { "" }
'''
    out = ps_run(script, str(pid), check=False).strip()
    return out if out else None

def win_quit_pids(pids: List[int], timeout_s: float = 20.0, force_after_timeout: bool = True):
    """Try CloseMainWindow first, then Stop-Process -Force if still alive after timeout."""
    if not pids:
        return
    # Ask nicely
    script_close = r'''
param([int[]]$pids)
$pids | ForEach-Object {
  try {
    $p = Get-Process -Id $_ -ErrorAction Stop
    # CloseMainWindow() returns $true when a WM_CLOSE was sent
    $null = $p.CloseMainWindow()
  } catch {}
}
'''
    # Feed pids as a PowerShell array string
    ps_run(script_close, ",".join(map(str, pids)), check=False)

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        alive = [pid for pid in pids if win_is_pid_alive(pid)]
        if not alive:
            return
        time.sleep(0.3)

    if force_after_timeout:
        script_kill = r'''
param([int[]]$pids)
$pids | ForEach-Object {
  try { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } catch {}
}
'''
        ps_run(script_kill, ",".join(map(str, pids)), check=False)

def win_is_pid_alive(pid: int) -> bool:
    script = r'''
$pid = [int]$args[0]
try { $null = Get-Process -Id $pid -ErrorAction Stop; "1" } catch { "0" }
'''
    out = ps_run(script, str(pid), check=False)
    return out.strip() == "1"

def win_resolve_launch_target(search: str, fallback_from_pid: Optional[str]) -> tuple[str, str]:
    """
    Try to resolve a launch target in this order:
      1) Executable path from a running instance (if available)
      2) Start Menu shortcut (.lnk) target
      3) UWP AppUserModelID (Appx) via Get-StartApps (launch with shell:AppsFolder)
      4) Let Start-Process resolve the name (PATH or app alias)
    Returns (mode, value) where mode is one of "exe", "uwp", "alias".
    """
    # 1) Existing running process path
    if fallback_from_pid:
        return ("exe", fallback_from_pid)

    # 2) Start Menu .lnk
    script_lnk = r'''
$search = $args[0]
$like = "*" + $search + "*"
$roots = @("$env:ProgramData\Microsoft\Windows\Start Menu\Programs",
           "$env:AppData\Microsoft\Windows\Start Menu\Programs")
$lnk = Get-ChildItem $roots -Recurse -Filter *.lnk -ErrorAction SilentlyContinue |
         Where-Object { $_.BaseName -like $like } |
         Sort-Object FullName |
         Select-Object -First 1 -ExpandProperty FullName
if ($lnk) {
  $wsh = New-Object -ComObject WScript.Shell
  $target = $wsh.CreateShortcut($lnk).TargetPath
  $target
}
'''
    lnk_target = ps_run(script_lnk, search, check=False).strip()
    if lnk_target:
        return ("exe", lnk_target)

    # 3) UWP / Appx
    script_uwp = r'''
$search = $args[0]
$like = "*" + $search + "*"
try {
  $app = Get-StartApps | Where-Object { $_.Name -like $like } | Select-Object -First 1
  if ($app) { $app.AppID }
} catch {}
'''
    appid = ps_run(script_uwp, search, check=False).strip()
    if appid:
        return ("uwp", appid)

    # 4) Alias / PATH program name
    return ("alias", search)

def win_launch(mode: str, value: str):
    if mode == "exe":
        # Explicit .exe path
        script = r'''
$exe = $args[0]
Start-Process -FilePath $exe | Out-Null
'''
        ps_run(script, value, check=True)
    elif mode == "uwp":
        # UWP AppUserModelID
        script = r'''
$appid = $args[0]
Start-Process ("shell:AppsFolder\" + $appid) | Out-Null
'''
        ps_run(script, value, check=True)
    else:
        # Let Windows resolve an alias or PATH program (e.g., "notepad", "chrome")
        script = r'''
$name = $args[0]
Start-Process $name | Out-Null
'''
        ps_run(script, value, check=True)

# -------------------------
# Orchestrator
# -------------------------

def restart_app(search: str):
    if is_macos():
        app_path = mac_mdfind_app(search)
        if not app_path:
            raise SystemExit(f"Could not find any application matching: {search!r}")
        bid = mac_bundle_id_for(app_path)
        if not bid or bid == "(null)":
            raise SystemExit(f"Could not determine bundle id for: {app_path}")
        print(f"[macOS] Matched: {app_path.name}  [{bid}]")
        was_running = mac_count_running_procs(bid) > 0
        if was_running:
            print("Quitting…")
            mac_quit_app(bid)
        else:
            print("App not running; will launch fresh.")
        print("Launching…")
        mac_launch_app(bid)
        print("Done.")
        return

    if is_windows():
        print(f"[Windows] Searching for running processes matching: {search!r}")
        pids = win_find_running_pids(search)
        exe_from_running = None
        if pids:
            # Prefer to relaunch the same executable we just closed
            for pid in pids:
                path = win_exec_path_for_pid(pid)
                if path:
                    exe_from_running = path
                    break
            print(f"Found {len(pids)} running instance(s); attempting graceful close…")
            win_quit_pids(pids)
        else:
            print("No running instance found; will launch fresh.")

        mode, target = win_resolve_launch_target(search, exe_from_running)
        print(f"Launching ({mode}): {target}")
        win_launch(mode, target)
        print("Done.")
        return

    raise SystemExit(f"Unsupported platform: {sys.platform}")


class AppRestarter:
    """
    Context manager that stops an app on enter and restarts it on exit.

    By default, it restarts only if the app was running at __enter__.
    Set restart_if_not_running=True to always launch on __exit__.

    Example:
        with AppRestarter("safari"):
            # App is closed here; do maintenance work...
            pass
        # App is relaunched here (if it was running before)
    """
    def __init__(self, search: str, *, timeout_s: float = 20.0,
                 force_after_timeout: bool = True, restart_if_not_running: bool = False):
        self.search = search
        self.timeout_s = timeout_s
        self.force_after_timeout = force_after_timeout
        self.restart_if_not_running = restart_if_not_running

        # Internal state
        self._platform = "mac" if sys.platform == "darwin" else ("win" if sys.platform.startswith("win") else "other")
        self._should_restart = False
        self._launch_info = None  # mac: ("mac", bundle_id) ; win: ("win", mode, target)

    def __enter__(self):
        if self._platform == "mac":
            app_path = mac_mdfind_app(self.search)
            if not app_path:
                raise RuntimeError(f"[macOS] Could not find any application matching: {self.search!r}")
            bid = mac_bundle_id_for(app_path)
            if not bid or bid == "(null)":
                raise RuntimeError(f"[macOS] Could not determine bundle id for: {app_path}")
            self._launch_info = ("mac", bid)

            was_running = mac_count_running_procs(bid) > 0
            if was_running:
                mac_quit_app(bid, timeout_s=self.timeout_s, force_after_timeout=self.force_after_timeout)
                self._should_restart = True
            else:
                self._should_restart = self.restart_if_not_running
            return self

        if self._platform == "win":
            pids = win_find_running_pids(self.search)
            exe_from_running = None
            if pids:
                for pid in pids:
                    path = win_exec_path_for_pid(pid)
                    if path:
                        exe_from_running = path
                        break
                win_quit_pids(pids, timeout_s=self.timeout_s, force_after_timeout=self.force_after_timeout)
                self._should_restart = True
            else:
                self._should_restart = self.restart_if_not_running

            mode, target = win_resolve_launch_target(self.search, exe_from_running)
            self._launch_info = ("win", mode, target)
            return self

        raise RuntimeError(f"Unsupported platform: {sys.platform}")

    def __exit__(self, exc_type, exc, tb):
        try:
            if not self._should_restart or not self._launch_info:
                return False  # don't suppress exceptions

            if self._platform == "mac":
                _, bid = self._launch_info
                mac_launch_app(bid)

            elif self._platform == "win":
                _, mode, target = self._launch_info
                win_launch(mode, target)

        finally:
            # Propagate any exception from the with-block
            return False

# -------------------------
# CLI
# -------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: restart_app.py <app-name-or-identifier-fragment>")
        print("Examples:")
        print("  restart_app.py safari")
        print("  restart_app.py com.google.Chrome")
        print('  restart_app.py "visual studio code"')
        print("  restart_app.py chrome")
        sys.exit(2)
    restart_app(" ".join(sys.argv[1:]))

