# Method 2 – hyperosunlocker.py (xzelleiv/xiaomi-bootloader-unlocker)

Single-window, single-token script. You paste one cookie value by hand and the
script handles the Beijing-midnight timing and the request burst itself.

Script location: `D:\Softwares\Xiamoi bootloader unlock script\Method 2\hyperosunlocker.py`

Key times (your PC is on India Standard Time, UTC+5:30):

| Event                      | Beijing (UTC+8) | Your local time (IST) |
|----------------------------|-----------------|-----------------------|
| Get token, start script    | 23:45           | 21:15                 |
| Script fires (default)     | 23:59:59.800    | 21:29:59.800          |
| Quota reset                | 00:00:00        | 21:30:00              |

---

## 1. One-time setup (already done)

A virtual environment lives at `Method 2\.venv` with ntplib, pytz, urllib3 and
colorama installed. Nothing else needs installing.

If you ever need to recreate it:

```cmd
cd "D:\Softwares\Xiamoi bootloader unlock script\Method 2"
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Also install a cookie editor extension in Firefox or Chrome (the common one is
called **Cookie-Editor**). Either browser works; Method 2 does not read the
browser itself.

---

## 2. Activate the venv

Open a **new** terminal window every time (old windows have a stale PATH).

**Command Prompt (cmd):**

```cmd
cd "D:\Softwares\Xiamoi bootloader unlock script\Method 2"
.venv\Scripts\activate.bat
```

**PowerShell:**

```powershell
cd "D:\Softwares\Xiamoi bootloader unlock script\Method 2"
Set-ExecutionPolicy -Scope Process Bypass -Force
.venv\Scripts\Activate.ps1
```

The `Set-ExecutionPolicy` line is required on this PC (the policy is currently
Restricted) and only affects that one window. To make it permanent instead, run
once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

You know it worked when the prompt starts with `(.venv)`. From then on
`python` means the venv's Python.

To leave the venv later, type `deactivate`.

---

## 3. Get the token (about 15 min before midnight Beijing, i.e. ~21:15 IST)

1. Log in at <https://new.c.mi.com/global> with the Mi account that is linked
   to the phone.
2. Open the cookie editor on that page and copy the **value** of the cookie
   named `new_bbs_serviceToken`.
   Copying the whole cookie string also works; the script extracts the value.

The cookie is tied to your browser session, so grab it fresh shortly before you
run the script.

---

## 4. Run the script

In the activated terminal from step 2:

```cmd
python hyperosunlocker.py
```

Paste the token when it asks and press Enter.

Alternative, non-interactive form:

```cmd
python hyperosunlocker.py --token "PASTE_VALUE_HERE"
```

---

## 5. What to expect on screen

1. **Account check** runs immediately. You want:
   `[account]: ready, requests will be sent.`
   Other outcomes:
   - `requests blocked until ...` or `account is younger than 30 days` → asks
     `continue (yes/no)?`
   - `already approved until ...` or `cookie expired, login again.` → exits.
2. **Beijing time** is fetched from NTP once, then the target time is printed
   (default 200 ms before midnight). Leave the window alone; it says `do not exit`.
3. **At the target** it fires requests: a burst of 30 at 30 ms spacing, then one
   every 100 ms until it gets a final answer.
   - Stops by itself on `approved`, `quota reached`, or `account blocked`.
   - If it keeps printing `request rejected` for more than a few seconds, press
     **Ctrl+C**. It will not stop on its own in that case.

---

## 6. On the phone afterwards (do this no matter what the script said)

1. Settings → My Account → **Sign out**. Restart the phone.
2. Sign back in and re-enable **Find Device**.
3. Settings → Additional settings → Developer options → **Mi Unlock status** →
   **Add account and device**.
4. Turn on **OEM unlocking**.
5. Run Mi Unlock on the PC. If the request went through, it shows the remaining
   waiting time. Unlocking wipes the phone.

If Mi Unlock will not log in, use the QR code / WhatsApp code option, or
MiUnlockTool from <https://github.com/MiForge/MiUnlockTool>.

---

## 7. Optional

**Dry run earlier in the day.** Steps 2–4 can be run at any time. The account
check and NTP fetch happen immediately, so you will know the token and network
work. Press Ctrl+C once it starts waiting, then get a fresh token at 21:15.

**NTP fallback.** If it prints `failed to fetch beijing time.`, rerun with the
servers Method 1 uses:

```cmd
python hyperosunlocker.py --ntp-servers ntp.aliyun.com,ntp.tencent.com,time.google.com,pool.ntp.org
```

**Useful flags** (defaults in brackets):

| Flag              | Meaning                                  | Default |
|-------------------|------------------------------------------|---------|
| `--phase-ms`      | ms before 00:00:00 Beijing to start      | 200     |
| `--burst-count`   | fast sends right after trigger           | 30      |
| `--burst-gap-ms`  | gap between burst sends                  | 30      |
| `--normal-gap-ms` | gap after the burst                      | 100     |
| `--ntp-servers`   | comma-separated NTP list                 | see script |

Each flag also has an env-var form prefixed `HYPEROS_` (e.g. `HYPEROS_TOKEN`,
`HYPEROS_PHASE_MS`).
