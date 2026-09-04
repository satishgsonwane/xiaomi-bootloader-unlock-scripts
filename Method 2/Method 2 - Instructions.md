# Method 2 – hyperosunlocker_multi.py / hyperosunlocker.py

Single-window, single-token method. You paste one cookie value by hand and the
script handles the Beijing-midnight timing and the requests itself.

Two scripts live in this folder:

- `hyperosunlocker_multi.py` (recommended): four workers in one window at
  staggered lead times, connections kept warm during the wait, lowest-latency
  NTP server with a re-sync before midnight, per-worker request cap, and a
  rehearsal mode that sends nothing.
- `hyperosunlocker.py`: the original single-worker script from
  xzelleiv/xiaomi-bootloader-unlocker.

Folder: `D:\Softwares\Xiamoi bootloader unlock script\Method 2`

Key times (your PC is on India Standard Time, UTC+5:30):

| Event                                   | Beijing (UTC+8)       | Your local time (IST) |
|-----------------------------------------|-----------------------|-----------------------|
| Get token, start script                 | 23:45                 | 21:15                 |
| NTP re-sync (multi script)              | 23:59:00              | 21:29:00              |
| Workers fire (default 400/250/150/50 ms)| 23:59:59.600 to .950  | 21:29:59.600 to .950  |
| Quota reset                             | 00:00:00              | 21:30:00              |

---

## 0. Quick start for beginners (IST times)

Midnight in Beijing is **9:30 PM in India**. Everything below is timed to that.
Keep the laptop plugged in and do not let the PC sleep.

**Any time during the day (practice run, nothing is sent)**

1. Install the **Cookie-Editor** extension in Firefox or Chrome.
2. Open Command Prompt: press `Win + R`, type `cmd`, press Enter.
3. Paste this line and press Enter (right-click or `Ctrl+V` pastes in cmd):
   ```cmd
   cd "D:\Softwares\Xiamoi bootloader unlock script\Method 2"
   ```
4. Paste this line and press Enter. The prompt should now start with `(.venv)`:
   ```cmd
   .venv\Scripts\activate.bat
   ```
5. Paste this line and press Enter. It counts down 40 seconds, "fires" four
   workers, and stops by itself. This is only a rehearsal; no request is sent:
   ```cmd
   python hyperosunlocker_multi.py --test-in-s 40
   ```
   If it ends with a `summary:` block, your setup works. Leave this window open.

**9:10 PM IST: get the token**

6. In the browser, open <https://new.c.mi.com/global> and log in with the Mi
   account that is linked to the phone.
7. Click the Cookie-Editor icon in the toolbar, find the row named
   `new_bbs_serviceToken`, and copy its **Value**.

**9:15 PM IST: start the script**

8. Back in the same Command Prompt (prompt still shows `(.venv)`), paste and
   press Enter:
   ```cmd
   python hyperosunlocker_multi.py
   ```
   If you opened a new window instead, repeat steps 3 and 4 first.
9. When it says `token:`, paste the value and press Enter.
10. Check the screen shows `account ready, requests can be sent` and a plan with
    `midnight (target)` at `00:00:00.000`. That is 9:30:00 PM on your clock.
    Now leave the window alone.

**What happens by itself**

| Your clock (IST) | What you see                                          |
|------------------|-------------------------------------------------------|
| 9:15 to 9:29 PM  | a `keep-alive` line from each worker every 30 s       |
| 9:29:00 PM       | `re-sync via ...: clock adjusted by ...`              |
| 9:29:56 PM       | `final warm-up` lines                                 |
| 9:29:59.6 PM     | `firing` and one line per request from each worker    |
| by 9:30:05 PM    | `summary:` and `final account status:`                |

**After 9:30 PM: read the result and do the phone steps**

11. `APPROVED` in the summary means it worked. `quota reached` means the daily
    quota was gone first; try again tomorrow. `rejected` on every line means
    the server said no each time; also try again tomorrow.
12. Whatever it said, on the phone: Settings → My Account → Sign out → restart
    → sign in → Find Device on → Settings → Additional settings → Developer
    options → Mi Unlock status → Add account and device → OEM unlocking on.
13. Run Mi Unlock on the PC. If the request went through, it shows how long
    you have to wait before unlocking.

**If something goes wrong**

- `cookie expired`: copy a fresh token (step 7) and run step 8 again. Must be
  done before 9:29 PM.
- `requests blocked until ...`: the account cannot apply tonight.
- Window closed by mistake before 9:30 PM: repeat steps 3, 4, 8 and 9.
- `no NTP server answered`: check the internet connection, then see section 7.

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

In the activated terminal from step 2. Recommended: the multi-worker script.

```cmd
python hyperosunlocker_multi.py
```

Paste the token when it asks and press Enter. It runs four workers in this one
window, firing 400, 250, 150 and 50 ms before midnight. Non-interactive form:

```cmd
python hyperosunlocker_multi.py --token "PASTE_VALUE_HERE"
```

The original single-worker script still works the same way if you prefer it:

```cmd
python hyperosunlocker.py
```

---

## 5. What to expect on screen (hyperosunlocker_multi.py)

1. **Clock sync.** Queries four nearby NTP servers and keeps the lowest-delay
   reply, e.g. `clock: time.cloudflare.com (delay 20 ms)`.
2. **Account check.** You want `account ready, requests can be sent`.
   - `requests blocked until ...` or `account is younger than 30 days` asks
     `continue anyway (yes/no)?`
   - `already approved ...` or `cookie expired ...` exits.
3. **Plan.** Prints the target midnight, each worker's fire time, and the
   burst / cap settings, then `do not close this window`.
4. **Waiting.** Each worker sends a `keep-alive` GET every 30 s so its
   connection stays open, then a `final warm-up` 3 s before it fires. The clock
   is re-synced 60 s before midnight (`clock adjusted by +x ms`). A
   `connection: Resetting dropped connection` line during the wait is harmless;
   you do not want to see one during firing.
5. **Firing.** One line per request: send time relative to midnight, round
   trip, and the reply. Each worker sends 5 quickly (30 ms apart), then every
   100 ms, up to 10 requests or 5 s past midnight, whichever comes first.
   - `APPROVED` stops all workers.
   - `quota reached` more than 1 s after midnight, `account blocked`, or
     `cookie expired` also stop all workers.
   - A `quota reached` reply to a request sent before midnight is ignored and
     the worker keeps going.
   - `rejected` keeps going until the cap.
6. **Summary** per worker, a final account status check, and the phone-steps
   reminder. A log file `hyperos_multi_<timestamp>.log` is written next to the
   script.

Ctrl+C stops all workers at any time.

The original `hyperosunlocker.py` prints a similar account check and target
time, then fires 30 requests at 30 ms spacing and one every 100 ms until it
gets a final answer. It does not stop on `rejected`, so press **Ctrl+C** after
a few seconds if that is all it prints.

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

**Rehearse earlier in the day (recommended).** Runs the whole flow against a
fake midnight 40 s away and sends only harmless status GETs, so nothing is
applied. No token is needed; with a real token it also confirms the account
state:

```cmd
python hyperosunlocker_multi.py --test-in-s 40
```

**Dry run at the real midnight.** `--dry-run` waits for the real midnight but
replaces the apply POST with a status GET.

**Different lead times.** One worker per value, in ms before midnight:

```cmd
python hyperosunlocker_multi.py --phases 500,300,150,0
```

**NTP fallback.** If it prints `no NTP server answered`, pass the servers
Method 1 uses:

```cmd
python hyperosunlocker_multi.py --ntp-servers ntp.aliyun.com,cn.pool.ntp.org,time.google.com,pool.ntp.org
```

**Flags for hyperosunlocker_multi.py** (each also settable as a `HYPEROS_*`
environment variable, e.g. `HYPEROS_TOKEN`, `HYPEROS_PHASES`):

| Flag               | Meaning                                                               | Default        |
|--------------------|-----------------------------------------------------------------------|----------------|
| `--phases`         | lead times in ms before midnight, one worker each                     | 400,250,150,50 |
| `--burst-count`    | fast sends per worker                                                 | 5              |
| `--burst-gap-ms`   | gap inside the burst                                                  | 30             |
| `--normal-gap-ms`  | gap after the burst                                                   | 100            |
| `--max-requests`   | per-worker cap, 0 = unlimited                                         | 10             |
| `--stop-after-ms`  | stop this long after midnight, 0 = never                              | 5000           |
| `--quota-grace-ms` | ignore quota-reached replies to requests sent earlier than this after midnight | 1000  |
| `--keepalive-s`    | seconds between keep-alive GETs                                       | 30             |
| `--final-warm-ms`  | last keep-alive this long before firing                               | 3000           |
| `--resync-s`       | NTP re-sync this long before midnight, 0 = off                        | 60             |
| `--ntp-servers`    | comma list, lowest delay wins                                         | cloudflare, pool.ntp.org, apple, google |
| `--dry-run`        | status GET instead of apply POST                                      | off            |
| `--test-in-s`      | rehearsal against a fake midnight N seconds away                      | off            |
| `--no-log`         | do not write a log file                                               | off            |

**Original script flags** (`hyperosunlocker.py`): `--phase-ms` (200),
`--burst-count` (30), `--burst-gap-ms` (30), `--normal-gap-ms` (100),
`--ntp-servers`.
