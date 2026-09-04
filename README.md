# Xiaomi / HyperOS Bootloader Unlock Scripts

Two community methods for getting a bootloader-unlock request accepted on
Xiaomi's global community server at the 00:00 Beijing quota reset. Works with
HyperOS 1, 2 and 3 (including devices that shipped with HyperOS 3).

This repository only collects the scripts and adds setup notes. The scripts
themselves were written by the people listed under **Credits**.

## Layout

| Path | What it is |
|------|------------|
| `Method 1/Avoid quota limit reached/` | Windows kit: `GetTokens.py` (grabs session tokens from Firefox/Chrome) + `NScript.py` (four timed request windows) |
| `Method 1/GetTokens for Gnome on Linux by Jenna-66/` | Same kit adapted for GNOME on Linux |
| `Method 1/Ping/Ping.bat` | Checks that the NTP and Mi API hosts are reachable |
| `Method 2/hyperosunlocker.py` | Original single-window script, token pasted by hand |
| `Method 2/hyperosunlocker_multi.py` | Multi-worker version of the above: staggered lead times, warm connections, nearby NTP, request cap, rehearsal mode |
| `Method 2/Method 2 - Instructions.md` | Step-by-step setup and run guide for Method 2, with a Python venv |

## Requirements

- Python 3.12+ (installed from python.org, not the Microsoft Store)
- Firefox and/or Chrome
- A Mi account that is linked to the phone and is at least 30 days old

## Method 1 (four windows, automatic token capture)

1. Open a terminal inside `Method 1/Avoid quota limit reached/` and run
   `py GetTokens.py`.
2. When prompted for the script name, drag `NScript.py` into the window.
3. Log in at <https://new.c.mi.com/global> in Firefox, press OK; then in Chrome,
   press OK. Chrome tokens may not be captured; the two Firefox lines are enough.
4. `token.txt` is written and four `NScript.py` windows open, each waiting for
   midnight Beijing with a different lead offset from `timeshift.txt`.
5. Start this 15 minutes or less before 00:00 Beijing (the cookie expires with
   the browser session).
6. Once the four requests have gone out, answer `No` to the continue prompt or
   close the windows so the script does not keep sending.

## Method 2 (one window, manual token)

See [`Method 2/Method 2 - Instructions.md`](Method%202/Method%202%20-%20Instructions.md)
for the full walkthrough. Short version:

```bash
cd "Method 2"
python -m venv .venv
.venv\Scripts\activate.bat        # Windows cmd
pip install -r requirements.txt
python hyperosunlocker_multi.py --test-in-s 40   # rehearsal, nothing is sent
python hyperosunlocker_multi.py                  # real run, paste the token
python hyperosunlocker.py                        # or the original single-worker script
```

`hyperosunlocker_multi.py` is a rework of the original that runs several workers
in one window at staggered lead times (default 400/250/150/50 ms), keeps the
TLS connections warm during the wait, picks the lowest-latency NTP server and
re-syncs before midnight, ignores a "quota reached" reply to a request that was
sent too early, and stops on its own after a per-worker cap.

## After the script runs (do this no matter what it printed)

1. Settings → My Account → Sign out. Restart the phone.
2. Sign in again, re-enable Find Device.
3. Settings → Additional settings → Developer options → Mi Unlock status →
   Add account and device. Enable OEM unlocking.
4. Run Mi Unlock on the PC. If the request went through it shows the remaining
   wait time. If Mi Unlock will not log in, try the QR / WhatsApp code option or
   [MiForge/MiUnlockTool](https://github.com/MiForge/MiUnlockTool).

**Unlocking erases all data on the phone.**

## Credits

All of the actual unlock logic comes from other people. This repo just keeps the
pieces together with setup notes.

- **Method 1** was shared on the XDA Forums thread that distributes the
  "Avoid quota limit reached" (AQLR) kit. As credited in that thread:
  - **dotKin** for the method and script
  - **nicogrimaldi** for the complete translation
  - **redmugen** for the detailed write-up
  - **byBestix** for `GetTokens.py` (GetTokens V2)
  - **Jenna-66** for the GNOME on Linux version of GetTokens
  - `NScript.py` carries the version tag `ARU_FHL_v070425` from that thread
- **Method 2** is [xzelleiv/xiaomi-bootloader-unlocker](https://github.com/xzelleiv/xiaomi-bootloader-unlocker),
  vendored here unchanged at commit `c616f18` (apart from adding `.venv/` to its
  `.gitignore`). That project in turn credits
  [offici5l/MiUnlockTool](https://github.com/offici5l/MiUnlockTool) for
  request/session handling ideas.
- [MiForge/MiUnlockTool](https://github.com/MiForge/MiUnlockTool) for the
  unlock-token retrieval alternative to Mi Unlock.

Neither upstream source ships an explicit license. The scripts are redistributed
here as-is, for convenience, with all rights remaining with their original
authors. If you are one of them and want your work removed or credited
differently, open an issue.

## Disclaimer

Not affiliated with Xiaomi. Use at your own risk. Automating requests against
Xiaomi's servers may be against their terms of service and can get an account
temporarily blocked.
