# Building check_up.py into executables (Windows / macOS / Linux)

## Important: you must build on each OS separately

PyInstaller (and every tool like it — cx_Freeze, Nuitka, py2exe, py2app)
**does not cross-compile**. A build run on macOS only produces a macOS
executable; it cannot produce a Windows `.exe`. So you need three
build runs, one on each actual OS (or use the GitHub Actions option at
the bottom, which does this for you automatically in the cloud).

The script itself needs no extra data files or resources bundled — it's
a single, self-contained .py file — so the build command is the same
shape everywhere.

---

## 1. Windows

On a Windows machine with Python 3.9+ installed:

```powershell
pip install pyinstaller
pyinstaller --onefile --name check_up --console check_up.py
```

Output: `dist\check_up.exe`

- `--console` keeps the terminal window open (required — the script uses
  `print()` and `input()` for the "Press Enter to exit" prompt).
- If you also want a custom icon: add `--icon check_up.ico`.
- Windows Defender / SmartScreen will likely flag a freshly-built,
  unsigned exe on first run ("Windows protected your PC"). That's normal
  for unsigned PyInstaller binaries, not a bug in the script. Click
  "More info" → "Run anyway", or code-sign the binary if you're
  distributing it widely.

## 2. macOS

On a Mac with Python 3.9+ installed:

```bash
pip3 install pyinstaller
pyinstaller --onefile --name check_up check_up.py
```

Output: `dist/check_up`

Run it:
```bash
chmod +x dist/check_up
./dist/check_up
```

- Gatekeeper will block the unsigned binary the first time
  ("cannot be opened because the developer cannot be verified"). Users
  can right-click → Open → Open anyway, or you can run
  `xattr -d com.apple.quarantine dist/check_up` after copying it to a
  new machine. For wide distribution you'd want an Apple Developer ID
  to sign + notarize it — not required just to run it on your own
  competition laptops.
- Build a native arm64 binary on Apple Silicon and a native x86_64
  binary on Intel Macs if you need both — PyInstaller builds for
  whichever architecture it's running on.

## 3. Linux

On a Linux machine with Python 3.9+ installed:

```bash
pip3 install pyinstaller
pyinstaller --onefile --name check_up check_up.py
```

Output: `dist/check_up`

```bash
chmod +x dist/check_up
./dist/check_up
```

- Build on the oldest glibc-based distro you plan to deploy to (e.g.
  Ubuntu 20.04), since a binary built on a newer glibc won't run on an
  older one. Building on a newer distro and running on an older one is
  the common failure mode; the reverse (build old, run new) works fine.

---

## Recommended: build all three automatically with GitHub Actions

Instead of hunting down a Windows, Mac, and Linux machine yourself, a
GitHub Actions matrix build will compile all three executables in the
cloud whenever you push. I've included a ready-to-use workflow file:
`build-executables.yml`.

Setup:
1. Create a GitHub repo, add `check_up.py` and the `.github/workflows/`
   folder (put `build-executables.yml` inside it).
2. Push to `main` (or trigger manually from the Actions tab).
3. Once the run finishes, download the three zipped executables from
   the run's "Artifacts" section — no need to own a Mac or a Windows PC.

---

## Testing checklist before handing these out to competitors

- [ ] Run each exe once on a clean copy of that OS (not the machine you
      built it on) to catch missing-dependency surprises.
- [ ] Confirm the HTML report opens in the default browser.
- [ ] Confirm `Press Enter to exit` keeps the window open on Windows
      (so results are visible instead of the console flashing shut).
- [ ] On Windows, click through the SmartScreen warning once so you know
      what invigilators/competitors will see.
