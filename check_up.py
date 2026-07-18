#!/usr/bin/env python3
"""
AI Tools Check — Laptop Inspection Script  v2.0
================================================
Run this on each laptop BEFORE the competition starts.
Opens a report in the browser. No internet needed. Nothing installed.

Usage:
  Windows : python ai_check.py        (or double-click)
  macOS   : python3 ai_check.py
  Linux   : python3 ai_check.py
"""

import sys, os, subprocess, platform, shutil, glob, socket, tempfile, webbrowser, datetime

if sys.platform == "win32":
    for _stream_name in ("stdout", "stderr"):
        _stream = getattr(sys, _stream_name)
        if _stream is None:
            continue  # can happen if frozen with --noconsole
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

OS       = platform.system()   # 'Windows' | 'Darwin' | 'Linux'
RESULTS  = []


# ══════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════

def run(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1
    except Exception as e:
        return "", str(e), 1


def record(step, name, passed, detail="", fix=""):
    RESULTS.append({"step": step, "name": name, "passed": passed,
                    "detail": detail, "fix": fix})
    tag = "  PASS" if passed else "  FAIL"
    print(f"{tag}  [{step}] {name}")
    if not passed and detail:
        print(f"        ↳ {detail}")


def port_open(port):
    """Return True if something is listening on 127.0.0.1:<port>."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except Exception:
        return False


def paths_exist(*paths):
    """Return the first existing path, or None."""
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def dir_nonempty(path):
    if not os.path.isdir(path):
        return False
    try:
        return any(True for _ in os.scandir(path))
    except PermissionError:
        return False


# ══════════════════════════════════════════════════════════════════
#  STEP 1 — Installed Applications & Binaries
# ══════════════════════════════════════════════════════════════════

# fmt: keyword → display name
BANNED_APPS = {
    "ollama":    "Ollama",
    "lmstudio":  "LM Studio",
    "gpt4all":   "GPT4All",
    "llamacpp":  "llama.cpp",
    "jan":       "Jan",           # checked carefully to avoid false positives
}

# Standalone binaries that must not exist anywhere in PATH
BANNED_BINARIES = [
    "ollama", "llama-server", "llama-cli", "llama-cpp",
    "lmstudio", "gpt4all",
]


def step1_installed_apps():
    print("\n── Step 1: Installed Applications & Binaries ──")

    # ── Windows ──────────────────────────────────────────────────
    if OS == "Windows":
        ps = (
            'Get-ItemProperty '
            'HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, '
            'HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, '
            'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* '
            '-ErrorAction SilentlyContinue '
            '| Select-Object -ExpandProperty DisplayName '
            '| Where-Object { $_ -ne $null }'
        )
        out, _, _ = run(f'powershell -NoProfile -Command "{ps}"')
        installed_lower = out.lower().replace(" ", "").replace("-", "")

        for keyword, display in BANNED_APPS.items():
            # "jan" only matches if it appears as a whole word to avoid false positives
            if keyword == "jan":
                found = any(
                    line.strip().lower() in ("jan", "jan ai")
                    for line in out.lower().splitlines()
                    if line.strip()
                )
            else:
                found = keyword in installed_lower
            record("Step 1", f"{display} not installed",
                   not found,
                   f"'{display}' found in Windows installed programs" if found else "",
                   f"Uninstall '{display}' via Settings → Apps → Installed apps")

        # Also check common Windows install dirs
        local = os.environ.get("LOCALAPPDATA", "")
        prog  = os.environ.get("PROGRAMFILES", "C:\\Program Files")
        prog86= os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")
        cursor_paths = [
            os.path.join(local, "Programs", "cursor", "Cursor.exe"),
            os.path.join(local, "cursor", "Cursor.exe"),
            os.path.join(prog,  "Cursor", "Cursor.exe"),
        ]
        cursor_found = any(os.path.exists(p) for p in cursor_paths)
        record("Step 1", "Cursor editor not installed",
               not cursor_found,
               "Cursor.exe found — Cursor is an AI-first editor, not permitted" if cursor_found else "",
               "Uninstall Cursor via Settings → Apps → Installed apps, then use VS Code")

    # ── macOS ─────────────────────────────────────────────────────
    elif OS == "Darwin":
        app_dirs = ["/Applications", os.path.expanduser("~/Applications")]
        all_apps_lower = []
        for d in app_dirs:
            if os.path.isdir(d):
                all_apps_lower += [
                    f.lower().replace(" ", "").replace("-", "").replace(".app", "")
                    for f in os.listdir(d)
                ]

        for keyword, display in BANNED_APPS.items():
            if keyword == "jan":
                found = "jan" in all_apps_lower   # exact .app name match (after stripping .app)
            else:
                found = any(keyword in a for a in all_apps_lower)
            record("Step 1", f"{display} not in /Applications",
                   not found,
                   f"'{display}.app' found in Applications folder" if found else "",
                   f"Drag '{display}' to Trash, empty Trash, then restart")

        # macOS launch agents (background daemons)
        for agent_dir in [os.path.expanduser("~/Library/LaunchAgents"), "/Library/LaunchAgents"]:
            if os.path.isdir(agent_dir):
                for f in os.listdir(agent_dir):
                    fl = f.lower()
                    for keyword in ["ollama", "lmstudio", "gpt4all"]:
                        if keyword in fl:
                            record("Step 1", f"No '{keyword}' background launch agent",
                                   False,
                                   f"Found: {os.path.join(agent_dir, f)}",
                                   "Run: launchctl unload " + os.path.join(agent_dir, f) +
                                   " && rm " + os.path.join(agent_dir, f))

        # Ollama model cache (macOS stores it here too)
        ollama_cache = os.path.expanduser("~/.ollama")
        if dir_nonempty(ollama_cache):
            record("Step 1", "~/.ollama model cache is empty",
                   False,
                   "~/.ollama exists with content — models may still be present",
                   "Run: rm -rf ~/.ollama")
        else:
            record("Step 1", "~/.ollama model cache is empty", True)

        # Cursor
        cursor_found = os.path.exists("/Applications/Cursor.app")
        record("Step 1", "Cursor editor not installed",
               not cursor_found,
               "Cursor.app found in /Applications — not permitted" if cursor_found else "",
               "Uninstall: drag Cursor.app to Trash and empty it")

    # ── Linux ─────────────────────────────────────────────────────
    elif OS == "Linux":
        # Check PATH for known binaries
        for binary in BANNED_BINARIES:
            p = shutil.which(binary)
            found = p is not None
            record("Step 1", f"'{binary}' not in PATH",
                   not found,
                   f"Found at: {p}" if found else "",
                   f"sudo rm {p}")

        # ~/.ollama model cache
        ollama_cache = os.path.expanduser("~/.ollama")
        if dir_nonempty(ollama_cache):
            record("Step 1", "~/.ollama model cache is empty",
                   False,
                   "~/.ollama exists with content — Ollama models still present",
                   "Run: rm -rf ~/.ollama")
        else:
            record("Step 1", "~/.ollama model cache is empty", True)

        # Jan stores data here
        jan_dir = os.path.expanduser("~/.jan")
        if dir_nonempty(jan_dir):
            record("Step 1", "~/.jan data folder is empty",
                   False, "~/.jan found — Jan AI may have been used",
                   "Run: rm -rf ~/.jan")
        else:
            record("Step 1", "~/.jan data folder is empty", True)

        # Cursor (Linux AppImage or installed)
        cursor_found = shutil.which("cursor") is not None or \
                       os.path.exists(os.path.expanduser("~/.local/share/cursor"))
        record("Step 1", "Cursor editor not installed",
               not cursor_found,
               "Cursor binary/data found" if cursor_found else "",
               "Remove the Cursor AppImage and ~/.local/share/cursor")

    # ── All OSes: PATH binary sweep ───────────────────────────────
    for binary in BANNED_BINARIES:
        p = shutil.which(binary)
        if p:
            record("Step 1", f"'{binary}' standalone binary not in PATH",
                   False,
                   f"Standalone binary at: {p}",
                   f"Delete: {'del' if OS == 'Windows' else 'rm'} \"{p}\"")


# ══════════════════════════════════════════════════════════════════
#  STEP 2 — Running Processes & Open Ports
# ══════════════════════════════════════════════════════════════════

# Process name fragments to scan for (exe-level, not display names)
BANNED_PROC_FRAGMENTS = [
    "ollama", "llama-server", "llama-cli", "llama.cpp",
    "lmstudio", "gpt4all", "jan-main", "jan-node",
]

# Ports used by local AI runtimes
BANNED_PORTS = {
    11434: "Ollama",
    1234:  "LM Studio",
    8080:  "Open WebUI / generic local LLM",
    5000:  "Local model server (generic)",
    3000:  "Open WebUI (alternate port)",
}


def step2_running_processes():
    print("\n── Step 2: Running Processes & Open Ports ──")

    if OS == "Windows":
        # tasklist shows image names (exe), not display names — use that
        out, _, _ = run("tasklist /FO CSV /NH")
        proc_lines = out.lower()
        for frag in BANNED_PROC_FRAGMENTS:
            # "jan" only as a whole exe name to avoid matching "january" etc.
            if frag == "jan-main" or frag == "jan-node":
                found = frag in proc_lines
            else:
                found = frag in proc_lines
            record("Step 2", f"Process '{frag}' not running",
                   not found,
                   f"'{frag}' appears in running processes" if found else "",
                   f"Kill in Task Manager → End Task, or: taskkill /F /IM {frag}.exe")

        # Also check wmic for LM Studio which runs as electron app
        out2, _, _ = run('wmic process get description,executablepath /format:csv 2>nul')
        lms_found = "lm studio" in out2.lower() or "lmstudio" in out2.lower()
        record("Step 2", "LM Studio process not running",
               not lms_found,
               "LM Studio process detected via WMIC" if lms_found else "",
               "Quit LM Studio from the system tray")

    elif OS == "Darwin":
        out, _, _ = run("ps -axo comm,args")
        lines = out.lower().splitlines()
        # Filter out our own process (works whether run as .py or as a
        # compiled exe under any filename)
        self_name = os.path.basename(sys.executable if getattr(sys, "frozen", False) else __file__).lower()
        lines = [l for l in lines if self_name not in l and "python" not in l[:20]]
        for frag in BANNED_PROC_FRAGMENTS:
            matching = [l for l in lines if frag in l]
            record("Step 2", f"Process '{frag}' not running",
                   len(matching) == 0,
                   f"Running: {matching[0][:80]}" if matching else "",
                   f"Run: pkill -f {frag}  (or quit from menu bar)")

    elif OS == "Linux":
        out, _, _ = run(
            "ps -axo comm,args --no-headers 2>/dev/null || ps aux 2>/dev/null"
        )
        self_name = os.path.basename(sys.executable if getattr(sys, "frozen", False) else __file__).lower()
        lines = [l for l in out.lower().splitlines()
                 if self_name not in l and "grep" not in l]
        for frag in BANNED_PROC_FRAGMENTS:
            matching = [l for l in lines if frag in l]
            record("Step 2", f"Process '{frag}' not running",
                   len(matching) == 0,
                   f"Running: {matching[0][:80]}" if matching else "",
                   f"Run: pkill -f {frag}")

    # Port checks — same for all OSes (uses Python socket, no shell needed)
    for port, service in BANNED_PORTS.items():
        listening = port_open(port)
        record("Step 2", f"Port {port} ({service}) not responding",
               not listening,
               f"Something is actively serving on localhost:{port}" if listening else "",
               f"Find and stop the process using port {port}: "
               f"{'netstat -ano | findstr :' + str(port) if OS == 'Windows' else 'lsof -i :' + str(port)}")


# ══════════════════════════════════════════════════════════════════
#  STEP 3 — Editor / IDE Extensions
# ══════════════════════════════════════════════════════════════════

# publisher.extension-id  (must match the folder prefix VS Code uses)
BANNED_VSCODE = [
    ("github",              "copilot",              "GitHub Copilot"),
    ("github",              "copilot-chat",         "GitHub Copilot Chat"),
    ("codeium",             "codeium",              "Codeium"),
    ("codeium",             "windsurf",             "Windsurf (Codeium)"),
    ("tabnine",             "tabnine-vscode",       "Tabnine"),
    ("continue",            "continue",             "Continue"),
    ("sourcegraph",         "cody-ai",              "Cody (Sourcegraph)"),
    ("amazonwebservices",   "amazon-q-vscode",      "Amazon Q"),
    ("amazonwebservices",   "codewhisperer",        "CodeWhisperer"),
    ("rubberduck-ai",       "rubberduck-vscode",    "Rubberduck"),
    ("ai-native",           "copilot",              "AI Native Copilot"),
]

BANNED_JB = [
    "github-copilot", "copilot", "tabnine", "codeium",
    "continue",       "ai-assistant", "full-line-code-completion",
    "cody",           "amazon-q",     "aws-toolkit",
]

BANNED_VIM_PLUGINS = [
    "copilot.vim", "codeium.vim", "avante.nvim",
    "tabnine-vim", "cody.nvim",   "fittencode",
]


def step3_editor_extensions():
    print("\n── Step 3: Editor / IDE Extensions ──")

    # ── VS Code: use CLI first, fall back to folder scan ─────────
    vscode_ext_list = None
    for cmd in ["code", "code-insiders", "codium"]:
        if shutil.which(cmd):
            out, _, rc = run(f"{cmd} --list-extensions 2>/dev/null")
            if rc == 0 and out:
                vscode_ext_list = out.lower().splitlines()
                break

    # Folder scan as fallback (and to catch extensions not reported by CLI)
    ext_scan_dirs = []
    if OS == "Windows":
        ext_scan_dirs = [
            os.path.expandvars(r"%USERPROFILE%\.vscode\extensions"),
            os.path.expandvars(r"%USERPROFILE%\.vscode-insiders\extensions"),
        ]
    else:
        ext_scan_dirs = [
            os.path.expanduser("~/.vscode/extensions"),
            os.path.expanduser("~/.vscode-insiders/extensions"),
            os.path.expanduser("~/.vscodium/extensions"),
        ]

    folder_exts = []
    for d in ext_scan_dirs:
        if os.path.isdir(d):
            folder_exts += [f.lower() for f in os.listdir(d) if os.path.isdir(os.path.join(d, f))]

    for publisher, ext_id, display in BANNED_VSCODE:
        full_id = f"{publisher}.{ext_id}"

        # CLI check
        cli_found = vscode_ext_list is not None and any(
            full_id in e for e in vscode_ext_list
        )

        # Folder check: VS Code names extension folders  publisher.ext-id-version
        folder_found = any(
            f.startswith(f"{publisher}.{ext_id}") for f in folder_exts
        )

        found = cli_found or folder_found
        record("Step 3", f"VS Code: '{display}' not installed",
               not found,
               f"Extension '{full_id}' detected ({'CLI' if cli_found else 'folder scan'})" if found else "",
               f"Open VS Code → Extensions (Ctrl+Shift+X) → search '{full_id}' → Uninstall (not Disable)")

    # GitHub sign-in check (Copilot can't work signed out)
    gh_token_paths = []
    if OS == "Windows":
        gh_token_paths = [
            os.path.expandvars(r"%APPDATA%\Code\User\globalStorage\github.authentication"),
            os.path.expandvars(r"%APPDATA%\Code - Insiders\User\globalStorage\github.authentication"),
        ]
    elif OS == "Darwin":
        gh_token_paths = [
            os.path.expanduser("~/Library/Application Support/Code/User/globalStorage/github.authentication"),
        ]
    else:
        gh_token_paths = [
            os.path.expanduser("~/.config/Code/User/globalStorage/github.authentication"),
        ]
    gh_signed_in = any(dir_nonempty(p) for p in gh_token_paths if os.path.isdir(p))
    record("Step 3", "VS Code: not signed into GitHub",
           not gh_signed_in,
           "GitHub authentication session found in VS Code profile" if gh_signed_in else "",
           "VS Code → Accounts (bottom-left) → Sign out of GitHub")

    # ── JetBrains ─────────────────────────────────────────────────
    jb_dirs = []
    if OS == "Windows":
        appdata = os.environ.get("APPDATA", "")
        jb_dirs = glob.glob(os.path.join(appdata, "JetBrains", "*", "plugins"))
    elif OS == "Darwin":
        jb_dirs = glob.glob(
            os.path.expanduser("~/Library/Application Support/JetBrains/*/plugins")
        )
    else:
        jb_dirs = glob.glob(os.path.expanduser("~/.local/share/JetBrains/*/plugins"))

    if jb_dirs:
        jb_clean = True
        for plugin_dir in jb_dirs:
            if not os.path.isdir(plugin_dir):
                continue
            installed_plugins = [d.lower() for d in os.listdir(plugin_dir)]
            for banned in BANNED_JB:
                hits = [p for p in installed_plugins if banned in p]
                if hits:
                    jb_clean = False
                    record("Step 3", f"JetBrains: '{banned}' plugin not present",
                           False,
                           f"Plugin folder '{hits[0]}' found in {plugin_dir}",
                           "Settings → Plugins → Installed → select plugin → Uninstall → restart IDE")
        if jb_clean:
            record("Step 3", "JetBrains: no banned plugins found", True)
    else:
        record("Step 3", "JetBrains IDE: not detected on this machine", True)

    # ── Cursor (all platforms already handled in Step 1, recheck here) ─
    # (already recorded in step1, skip duplicate)

    # ── Vim / Neovim ──────────────────────────────────────────────
    if OS != "Windows":
        vim_dirs = [
            os.path.expanduser("~/.vim/pack"),
            os.path.expanduser("~/.vim/plugged"),
            os.path.expanduser("~/.vim/bundle"),
            os.path.expanduser("~/.config/nvim"),
            os.path.expanduser("~/.local/share/nvim/site/pack"),
            os.path.expanduser("~/.local/share/nvim/lazy"),   # lazy.nvim
        ]
        vim_clean = True
        for vim_dir in vim_dirs:
            if not os.path.isdir(vim_dir):
                continue
            for root, dirs, files in os.walk(vim_dir):
                rl = root.lower()
                for banned in BANNED_VIM_PLUGINS:
                    if banned.lower().replace(".vim", "").replace(".nvim", "") in rl:
                        vim_clean = False
                        record("Step 3", f"Vim/Neovim: '{banned}' not installed",
                               False,
                               f"Found at: {root}",
                               f"Delete: rm -rf \"{root}\"")
        if vim_clean:
            record("Step 3", "Vim/Neovim: no banned plugins detected", True)

    # ── Browser extensions (Chrome / Edge / Brave / Firefox) ──────
    # Checks for known AI extension IDs in the browser profile
    CHROME_AI_EXT_IDS = {
        "fenlkokljinaifpecimfpfgkpagnkioi": "Codeium (Chrome)",
        "bocnokknednjolfkbbjbfmhbakcclfpe": "Tabnine (Chrome)",
        "ghbmnnjooekpmoecnnnilnnbdlolhkhi": "Google Docs Offline (safe — just an example)",
        "gjdnpnmkdgiblniemkohpkgogfjpbahl": "Amazon CodeWhisperer (Chrome)",
        "dnmchlhlnnboecmcfbljckcmpjmoeenj": "GitHub Copilot for Web",
    }
    # Remove the safe example
    CHROME_AI_EXT_IDS = {
        "fenlkokljinaifpecimfpfgkpagnkioi": "Codeium (Chrome)",
        "bocnokknednjolfkbbjbfmhbakcclfpe": "Tabnine (Chrome)",
        "gjdnpnmkdgiblniemkohpkgogfjpbahl": "Amazon CodeWhisperer (Chrome)",
        "dnmchlhlnnboecmcfbljckcmpjmoeenj": "GitHub Copilot for Web",
    }

    chrome_ext_base = []
    if OS == "Windows":
        chrome_ext_base = [
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Extensions"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Extensions"),
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\User Data\Default\Extensions"),
        ]
    elif OS == "Darwin":
        chrome_ext_base = [
            os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/Extensions"),
            os.path.expanduser("~/Library/Application Support/Microsoft Edge/Default/Extensions"),
            os.path.expanduser("~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Extensions"),
        ]
    else:
        chrome_ext_base = [
            os.path.expanduser("~/.config/google-chrome/Default/Extensions"),
            os.path.expanduser("~/.config/chromium/Default/Extensions"),
            os.path.expanduser("~/.config/microsoft-edge/Default/Extensions"),
            os.path.expanduser("~/.config/BraveSoftware/Brave-Browser/Default/Extensions"),
        ]

    browser_clean = True
    for ext_dir in chrome_ext_base:
        if not os.path.isdir(ext_dir):
            continue
        installed_ids = [d.lower() for d in os.listdir(ext_dir)]
        for ext_id, display in CHROME_AI_EXT_IDS.items():
            if ext_id.lower() in installed_ids:
                browser_clean = False
                record("Step 3", f"Browser: '{display}' extension not installed",
                       False,
                       f"Extension ID {ext_id} found in {ext_dir}",
                       "Open chrome://extensions → find the extension → Remove")

    if browser_clean:
        record("Step 3", "Browser: no banned AI extensions detected", True)


# ══════════════════════════════════════════════════════════════════
#  STEP 4 — Local Web UIs & Service Data
# ══════════════════════════════════════════════════════════════════

def step4_local_webuis():
    print("\n── Step 4: Local Web UIs & Service Data ──")

    # Port checks (belt-and-suspenders — also done in step 2)
    for port, service in BANNED_PORTS.items():
        listening = port_open(port)
        record("Step 4", f"Port {port} ({service}) not listening",
               not listening,
               f"Active listener on localhost:{port}" if listening else "",
               f"Kill the process using this port")

    # Open WebUI data directories
    webui_dirs = []
    if OS == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")
        webui_dirs = [
            os.path.join(local,   "open-webui"),
            os.path.join(appdata, "open-webui"),
        ]
    else:
        webui_dirs = [
            os.path.expanduser("~/.local/share/open-webui"),
            os.path.expanduser("~/.open-webui"),
            "/opt/open-webui",
            "/usr/local/share/open-webui",
        ]

    found_webui = next((d for d in webui_dirs if os.path.isdir(d)), None)
    record("Step 4", "Open WebUI not installed",
           found_webui is None,
           f"Open WebUI data directory found at: {found_webui}" if found_webui else "",
           "Stop Open WebUI service and delete the data directory")

    # Check for Docker containers running AI services (best-effort)
    if shutil.which("docker"):
        out, _, rc = run("docker ps --format '{{.Image}} {{.Ports}}' 2>/dev/null", timeout=5)
        if rc == 0:
            keywords = ["ollama", "llama", "open-webui", "lmstudio", "gpt4all"]
            for kw in keywords:
                if kw in out.lower():
                    record("Step 4", f"Docker: no '{kw}' container running",
                           False,
                           f"Docker container matching '{kw}' is running",
                           f"Run: docker stop $(docker ps -q --filter ancestor={kw})")
            else:
                record("Step 4", "Docker: no banned AI containers running", True)
    else:
        record("Step 4", "Docker: not installed (nothing to check)", True)

    # WSL (Windows Subsystem for Linux) — could hide a Linux ollama
    if OS == "Windows" and shutil.which("wsl"):
        out, _, rc = run('wsl -- ps aux 2>/dev/null | grep -iE "ollama|llama|lmstudio" | grep -v grep', timeout=10)
        found_in_wsl = bool(out.strip())
        record("Step 4", "WSL: no banned AI processes running inside WSL",
               not found_in_wsl,
               f"Found inside WSL: {out.splitlines()[0][:80]}" if found_in_wsl else "",
               "Inside WSL terminal: pkill -f ollama")


# ══════════════════════════════════════════════════════════════════
#  HTML REPORT
# ══════════════════════════════════════════════════════════════════

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI Check — {hostname}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,'Segoe UI',sans-serif;background:#07090f;color:#e2e8f0;min-height:100vh}}
.hero{{padding:36px 32px 24px;border-bottom:1px solid #1a2236;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}}
.hero h1{{font-size:clamp(24px,5vw,44px);font-weight:800;letter-spacing:-1px;color:#f8fafc}}
.sub{{font-family:monospace;font-size:12px;color:#475569;margin-top:5px}}
.verdict{{font-size:clamp(16px,3vw,28px);font-weight:800;padding:12px 28px;border-radius:10px;letter-spacing:1px;text-transform:uppercase}}
.verdict.pass{{background:#052e16;color:#4ade80;border:2px solid #166534}}
.verdict.fail{{background:#2d0a0a;color:#f87171;border:2px solid #7f1d1d}}
.stats{{display:flex;gap:10px;padding:18px 32px;border-bottom:1px solid #1a2236;flex-wrap:wrap}}
.stat{{background:#0f1729;border:1px solid #1a2236;border-radius:10px;padding:12px 18px;min-width:90px;text-align:center}}
.stat .n{{font-size:26px;font-weight:800;line-height:1}}
.stat .l{{font-size:10px;color:#64748b;margin-top:3px;text-transform:uppercase;letter-spacing:.5px}}
.n.blue{{color:#818cf8}}.n.green{{color:#4ade80}}.n.red{{color:#f87171}}
.steps{{padding:20px 32px;display:flex;flex-direction:column;gap:14px}}
.card{{border-radius:11px;overflow:hidden;border:1px solid #1a2236}}
.card-head{{display:flex;align-items:center;gap:12px;padding:13px 16px;background:#0f1729}}
.card-head .ico{{font-size:18px}}
.card-head .title{{font-weight:700;font-size:14px;color:#f1f5f9;flex:1}}
.badge{{font-size:10px;font-weight:700;padding:3px 9px;border-radius:20px;text-transform:uppercase;letter-spacing:.4px}}
.bp{{background:#052e16;color:#4ade80}}.bf{{background:#2d0a0a;color:#f87171}}
.row{{display:flex;align-items:flex-start;gap:10px;padding:9px 16px;border-top:1px solid #07090f;font-size:12.5px}}
.row:hover{{background:#0f1729}}
.ri{{font-size:13px;margin-top:1px;flex-shrink:0}}
.rn{{color:#cbd5e1;flex:1;line-height:1.45}}
.rd{{font-family:monospace;font-size:11px;color:#f87171;margin-top:3px}}
.rf{{font-size:11px;color:#fbbf24;margin-top:3px}}
.foot{{padding:18px 32px;font-family:monospace;font-size:11px;color:#1e2a3a;border-top:1px solid #1a2236}}
@media(max-width:600px){{.hero,.stats,.steps{{padding-left:14px;padding-right:14px}}}}
</style>
</head>
<body>
<div class="hero">
  <div>
    <h1>AI Tools Check</h1>
    <div class="sub">{hostname} &nbsp;·&nbsp; {os_name} &nbsp;·&nbsp; {ts}</div>
  </div>
  <div class="verdict {vc}">{vt}</div>
</div>
<div class="stats">
  <div class="stat"><div class="n blue">{total}</div><div class="l">Checks</div></div>
  <div class="stat"><div class="n green">{passed}</div><div class="l">Passed</div></div>
  <div class="stat"><div class="n red">{failed}</div><div class="l">Failed</div></div>
</div>
<div class="steps">{cards}</div>
<div class="foot">ai_check.py v2.0 &nbsp;·&nbsp; Python {pyver} &nbsp;·&nbsp; {ts}</div>
</body></html>"""


def build_report(results, hostname, os_name):
    total  = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed
    vc = "pass" if failed == 0 else "fail"
    vt = "✓ CLEARED" if failed == 0 else f"✗ {failed} ISSUE{'S' if failed > 1 else ''} FOUND"

    STEP_META = {
        "Step 1": ("📦", "Installed Applications & Binaries"),
        "Step 2": ("⚙️",  "Running Processes & Open Ports"),
        "Step 3": ("🧩", "Editor / IDE Extensions"),
        "Step 4": ("🌐", "Local Web UIs & Containers"),
    }

    cards = ""
    for step, (ico, title) in STEP_META.items():
        rows = [r for r in results if r["step"] == step]
        if not rows:
            continue
        ok = all(r["passed"] for r in rows)
        badge_cls = "bp" if ok else "bf"
        badge_txt = "ALL CLEAR" if ok else f"{sum(1 for r in rows if not r['passed'])} FAILED"

        row_html = ""
        for r in rows:
            icon = "✅" if r["passed"] else "❌"
            det  = f'<div class="rd">↳ {r["detail"]}</div>' if r["detail"] and not r["passed"] else ""
            fix  = f'<div class="rf">⚡ {r["fix"]}</div>'   if r["fix"]    and not r["passed"] else ""
            row_html += f'<div class="row"><div class="ri">{icon}</div><div class="rn">{r["name"]}{det}{fix}</div></div>'

        cards += (f'<div class="card">'
                  f'<div class="card-head"><div class="ico">{ico}</div>'
                  f'<div class="title">{step} — {title}</div>'
                  f'<div class="badge {badge_cls}">{badge_txt}</div></div>'
                  f'{row_html}</div>')

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return HTML.format(
        hostname=hostname, os_name=os_name, ts=ts,
        vc=vc, vt=vt, total=total, passed=passed, failed=failed,
        cards=cards, pyver=platform.python_version()
    )


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    print("=" * 58)
    print("  AI Tools Check  v2.0 — Competition Laptop Inspection")
    print("=" * 58)
    print(f"  OS       : {OS}")
    print(f"  Hostname : {platform.node()}")
    print(f"  Python   : {platform.python_version()}")
    print(f"  Time     : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 58)

    step1_installed_apps()
    step2_running_processes()
    step3_editor_extensions()
    step4_local_webuis()

    passed = sum(1 for r in RESULTS if r["passed"])
    failed = len(RESULTS) - passed

    print("\n" + "=" * 58)
    if failed == 0:
        print(f"  RESULT : ✅  ALL CLEAR  ({passed}/{len(RESULTS)} checks passed)")
    else:
        print(f"  RESULT : ❌  {failed} ISSUE(S) FOUND  ({passed}/{len(RESULTS)} checks passed)")
        print()
        print("  Issues:")
        for r in RESULTS:
            if not r["passed"]:
                print(f"    • [{r['step']}] {r['name']}")
                if r["detail"]: print(f"           {r['detail']}")
    print("=" * 58)

    hostname = platform.node() or "unknown-host"
    html = build_report(RESULTS, hostname, OS)

    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=".html",
        prefix=f"ai_check_{hostname.replace(' ','_')}_",
        mode="w", encoding="utf-8"
    )
    tmp.write(html)
    tmp.close()

    print(f"\n  Report  : {tmp.name}")
    webbrowser.open(f"file://{tmp.name}")
    print("\n  ⚠  Show the browser report to the invigilator before closing this window.")
    input("\n  Press Enter to exit...")


if __name__ == "__main__":
    main()
