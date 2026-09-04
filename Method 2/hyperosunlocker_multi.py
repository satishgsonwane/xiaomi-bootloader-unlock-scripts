#!/usr/bin/env python3
"""hyperosunlocker_multi.py

Multi-worker variant of hyperosunlocker.py (xzelleiv/xiaomi-bootloader-unlocker).
Same API endpoints, cookie format and result codes as the original. What it adds:

  * N workers in one window (default 4), each firing at its own lead time before
    00:00:00 Beijing, each on its own TLS connection with its own device id.
  * Clock taken from the lowest-delay reply among several nearby NTP servers,
    then re-synced shortly before the target to cancel drift.
  * Keep-alive GETs during the wait so the midnight POST reuses a warm
    connection instead of paying a fresh TCP + TLS handshake.
  * A "quota reached" reply to a request sent before (or just after) midnight is
    treated as "too early" and the worker keeps going instead of quitting.
  * Per-worker request cap and a stop-after-midnight limit, so the script stops
    on its own instead of hammering the server until Ctrl+C.
  * --test-in-s rehearses the whole flow against a fake target a few seconds
    away, sending only harmless status GETs. No token needed.

Usage:
  python hyperosunlocker_multi.py                    # prompts for the token
  python hyperosunlocker_multi.py --token "..." --phases 400,250,150,50
  python hyperosunlocker_multi.py --test-in-s 40     # rehearsal, nothing applied
"""

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import threading
import time
from datetime import datetime, timedelta, timezone

import ntplib
import pytz
import urllib3
from colorama import Fore, Style, init
from urllib3.util import Retry

init(autoreset=True)
G, Y, R, B, C = Fore.GREEN, Fore.YELLOW, Fore.RED, Fore.BLUE, Fore.CYAN
BOLD = Style.BRIGHT

BEIJING = pytz.timezone("Asia/Shanghai")
DEFAULT_NTP = "time.cloudflare.com,pool.ntp.org,time.apple.com,time.google.com"
FALLBACK_NTP = "ntp.aliyun.com,cn.pool.ntp.org,edu.ntp.org.cn,ntp0.ntp-servers.net"
DEFAULT_STATUS_URL = "https://sgp-api.buy.mi.com/bbs/api/global/user/bl-switch/state"
DEFAULT_APPLY_URL = "https://sgp-api.buy.mi.com/bbs/api/global/apply/bl-auth"


# ----------------------------------------------------------------------------- config
def env_or(name, default):
    return os.getenv(name, default)


def parse_args():
    p = argparse.ArgumentParser(
        description="multi-worker HyperOS bootloader unlock request runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--token", default=env_or("HYPEROS_TOKEN", ""),
                   help="new_bbs_serviceToken value or full cookie string (prompted if empty)")
    p.add_argument("--phases", default=env_or("HYPEROS_PHASES", "400,250,150,50"),
                   help="comma list of lead times in ms before midnight; one worker per value")
    p.add_argument("--burst-count", type=int, default=int(env_or("HYPEROS_BURST_COUNT", "5")),
                   help="requests per worker sent at --burst-gap-ms spacing before slowing down")
    p.add_argument("--burst-gap-ms", type=float, default=float(env_or("HYPEROS_BURST_GAP_MS", "30")),
                   help="gap between requests inside the burst")
    p.add_argument("--normal-gap-ms", type=float, default=float(env_or("HYPEROS_NORMAL_GAP_MS", "100")),
                   help="gap between requests after the burst")
    p.add_argument("--max-requests", type=int, default=int(env_or("HYPEROS_MAX_REQUESTS", "10")),
                   help="per-worker cap on apply requests (0 = unlimited)")
    p.add_argument("--stop-after-ms", type=float, default=float(env_or("HYPEROS_STOP_AFTER_MS", "5000")),
                   help="stop sending this long after midnight (0 = no limit)")
    p.add_argument("--quota-grace-ms", type=float, default=float(env_or("HYPEROS_QUOTA_GRACE_MS", "1000")),
                   help="quota-reached replies to requests sent earlier than this after midnight are ignored")
    p.add_argument("--keepalive-s", type=float, default=float(env_or("HYPEROS_KEEPALIVE_S", "30")),
                   help="seconds between keep-alive GETs while waiting")
    p.add_argument("--final-warm-ms", type=float, default=float(env_or("HYPEROS_FINAL_WARM_MS", "3000")),
                   help="send the last keep-alive this long before the worker fires")
    p.add_argument("--resync-s", type=float, default=float(env_or("HYPEROS_RESYNC_S", "60")),
                   help="re-sync the clock from NTP this many seconds before midnight (0 = off)")
    p.add_argument("--ntp-servers", default=env_or("HYPEROS_NTP_SERVERS", DEFAULT_NTP),
                   help="comma list of NTP servers; all are queried, lowest delay wins")
    p.add_argument("--ntp-samples", type=int, default=2, help="queries per NTP server")
    p.add_argument("--status-url", default=env_or("HYPEROS_STATUS_URL", DEFAULT_STATUS_URL))
    p.add_argument("--apply-url", default=env_or("HYPEROS_APPLY_URL", DEFAULT_APPLY_URL))
    p.add_argument("--user-agent", default=env_or("HYPEROS_USER_AGENT", "okhttp/4.12.0"))
    p.add_argument("--version-code", default=env_or("HYPEROS_VERSION_CODE", "500411"))
    p.add_argument("--version-name", default=env_or("HYPEROS_VERSION_NAME", "5.4.11"))
    p.add_argument("--dry-run", action="store_true",
                   help="replace the apply POST with a status GET (nothing is applied)")
    p.add_argument("--test-in-s", type=float, default=0,
                   help="rehearsal: treat now + N seconds as midnight; implies --dry-run, token optional")
    p.add_argument("--log", default=None, help="log file path (default: hyperos_multi_<timestamp>.log)")
    p.add_argument("--no-log", action="store_true", help="do not write a log file")
    return p.parse_args()


# ----------------------------------------------------------------------------- helpers
class Log:
    """thread-safe console + file logger"""

    def __init__(self, path):
        self.lock = threading.Lock()
        self.fh = open(path, "a", encoding="utf-8") if path else None

    def __call__(self, msg, color="", tag=""):
        with self.lock:
            print(f"{color}{tag}{msg}", flush=True)
            if self.fh:
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self.fh.write(f"{ts} {tag}{msg}\n")
                self.fh.flush()


def hook_urllib3(log):
    """surface connection open / reconnect events so the warm-up can be verified"""

    class Handler(logging.Handler):
        def emit(self, record):
            msg = record.getMessage()
            if "Resetting dropped connection" in msg or "Starting new HTTPS connection" in msg:
                log(f"connection: {msg}", Y, f"[{threading.current_thread().name}] ")

    lg = logging.getLogger("urllib3")
    lg.setLevel(logging.DEBUG)
    lg.addHandler(Handler())
    lg.propagate = False


def epoch_to_bj(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone(BEIJING)


def fmt(epoch):
    return epoch_to_bj(epoch).strftime("%H:%M:%S.%f")[:-3]


def fmt_full(epoch):
    return epoch_to_bj(epoch).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def generate_device_id():
    return hashlib.sha1(f"{random.random()}-{time.time()}".encode("utf-8")).hexdigest().upper()


def extract_service_token(raw):
    raw = raw.strip()
    m = re.search(r"new_bbs_serviceToken=([^;]+)", raw)
    return m.group(1).strip() if m else raw


def resolve_token(cli_token, test_mode):
    token = extract_service_token(cli_token)
    if token:
        return token
    if test_mode:
        print("test mode: no token given, using a dummy one (status replies will say expired, that is fine)")
        return "TEST"
    print("paste the new_bbs_serviceToken value, or the full cookie string")
    token = extract_service_token(input("token: "))
    if not token:
        raise SystemExit("empty token")
    return token


def build_cookie_header(token, device_id, version_code, version_name):
    return (f"new_bbs_serviceToken={token};versionCode={version_code};"
            f"versionName={version_name};deviceId={device_id};")


def make_pool(user_agent):
    return urllib3.PoolManager(
        maxsize=1,
        retries=Retry(total=2, connect=2, read=0, status=0, redirect=0, raise_on_status=False),
        timeout=urllib3.Timeout(connect=2.0, read=6.0),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": user_agent,
            "Connection": "keep-alive",
        },
    )


def do_request(http, method, url, cookie, body=None):
    """returns (payload dict or None, error string or None)"""
    if method == "POST" and body is None:
        body = b'{"is_retry":true}'
    try:
        resp = http.request(method, url, headers={"Cookie": cookie}, body=body, preload_content=False)
    except Exception as exc:
        return None, f"network error: {exc}"
    try:
        raw = resp.data
    finally:
        resp.release_conn()
    try:
        return json.loads(raw.decode("utf-8")), None
    except Exception as exc:
        return None, f"bad json ({exc}): {raw[:200]!r}"


def status_summary(payload):
    if payload is None:
        return "no reply"
    code = payload.get("code")
    if code == 100004:
        return "cookie expired (100004)"
    data = payload.get("data") or {}
    if "is_pass" in data:
        return (f"is_pass={data.get('is_pass')} button_state={data.get('button_state')} "
                f"deadline={data.get('deadline_format', '')}")
    return f"code={code} msg={payload.get('msg') or payload.get('message') or ''}"


def classify_status(payload):
    """-> (state, message)  state in ready/blocked/young/approved/expired/unknown/none"""
    if payload is None:
        return "none", "no reply from status endpoint"
    if payload.get("code") == 100004:
        return "expired", "cookie expired, log in again and grab a fresh token"
    data = payload.get("data") or {}
    is_pass, bs, dl = data.get("is_pass"), data.get("button_state"), data.get("deadline_format", "")
    if is_pass == 4 and bs == 1:
        return "ready", "account ready, requests can be sent"
    if is_pass == 4 and bs == 2:
        return "blocked", f"requests blocked until {dl}"
    if is_pass == 4 and bs == 3:
        return "young", "account is younger than 30 days"
    if is_pass == 1:
        return "approved", f"already approved, unlock allowed until {dl}"
    return "unknown", f"unknown state: {payload}"


def startup_gate(state, msg, log, test_mode):
    if state == "ready":
        log(msg, G)
        return
    if state in ("blocked", "young"):
        log(msg, Y)
        if input("continue anyway (yes/no)? ").strip().lower() in ("y", "yes"):
            return
        raise SystemExit("stopped by user")
    if test_mode:
        log(f"{msg} -- test mode, continuing anyway", Y)
        return
    raise SystemExit(msg)


# ----------------------------------------------------------------------------- clock
class BeijingClock:
    """monotonic clock pinned to the best NTP sample seen"""

    def __init__(self):
        self.ref = None  # (utc epoch, perf_counter tick) - tuple swap is atomic
        self.source = None
        self.delay_ms = None

    def now_epoch(self):
        utc, tick = self.ref
        return utc + (time.perf_counter() - tick)

    def sync(self, servers, samples, log):
        """query every server, keep the lowest-delay sample. returns jump in ms, or None on failure"""
        client = ntplib.NTPClient()
        best = None
        for server in servers:
            for _ in range(samples):
                try:
                    r = client.request(server, version=3, timeout=2)
                    tick = time.perf_counter()
                except Exception as exc:
                    log(f"ntp {server}: {type(exc).__name__}", Y)
                    break
                cand = (r.delay, server, r.dest_time + r.offset, tick)
                if best is None or cand[0] < best[0]:
                    best = cand
        if best is None:
            return None
        delay, server, utc, tick = best
        jump_ms = 0.0
        if self.ref is not None:
            jump_ms = ((utc + (time.perf_counter() - tick)) - self.now_epoch()) * 1000
        self.ref = (utc, tick)
        self.source, self.delay_ms = server, delay * 1000
        return jump_ms


# ----------------------------------------------------------------------------- worker
class Worker(threading.Thread):
    def __init__(self, idx, phase_ms, cfg, clock, log, stop_all, midnight):
        super().__init__(name=f"w{idx}", daemon=True)
        self.idx, self.phase_ms, self.cfg = idx, phase_ms, cfg
        self.clock, self._log, self.stop_all, self.midnight = clock, log, stop_all, midnight
        self.fire_at = midnight - phase_ms / 1000.0
        self.tag = f"[w{idx} -{phase_ms:.0f}ms] "
        self.device_id = generate_device_id()
        self.cookie = build_cookie_header(cfg.token, self.device_id, cfg.version_code, cfg.version_name)
        self.http = make_pool(cfg.user_agent)
        self.sent = 0
        self.result = "not started"

    def log(self, msg, color=""):
        self._log(msg, color, self.tag)

    def stopped(self):
        return self.stop_all.is_set()

    def run(self):
        try:
            self.wait_phase()
            if self.stopped():
                self.result = "stopped before firing"
                return
            self.fire_phase()
        except Exception as exc:
            self.result = f"crashed: {exc!r}"
            self.log(self.result, R)

    # -- waiting -----------------------------------------------------------------
    def keepalive(self, label):
        t0 = self.clock.now_epoch()
        payload, err = do_request(self.http, "GET", self.cfg.status_url, self.cookie)
        dt = (self.clock.now_epoch() - t0) * 1000
        if err:
            self.log(f"{label}: {err}", Y)
            return
        self.log(f"{label}: {dt:.0f} ms, {status_summary(payload)}")
        if classify_status(payload)[0] == "expired" and not self.cfg.test_mode:
            self.log("cookie expired during the wait, stopping everything", R)
            self.stop_all.set()

    def wait_phase(self):
        final_lead = self.cfg.final_warm_ms / 1000.0
        last_ka = None
        final_done = False
        while not self.stopped():
            remaining = self.fire_at - self.clock.now_epoch()
            if remaining <= 0:
                return
            if not final_done and remaining <= final_lead:
                self.keepalive("final warm-up")
                final_done = True
                continue
            if (not final_done and remaining > final_lead + 2.0
                    and (last_ka is None or time.perf_counter() - last_ka >= self.cfg.keepalive_s)):
                self.keepalive("keep-alive")
                last_ka = time.perf_counter()
                continue
            if remaining > 5.0:
                time.sleep(0.5)
            elif remaining > 0.5:
                time.sleep(0.02)
            elif remaining > 0.005:
                time.sleep(0.0005)
            # last few ms: spin

    # -- firing ------------------------------------------------------------------
    def classify(self, payload, sent_at):
        """-> (verdict, message)  verdict in approved/quota/blocked/expired/recheck/retry"""
        if self.cfg.dry_run:
            return "retry", f"dry-run reply: {status_summary(payload)}"
        code = payload.get("code")
        data = payload.get("data") or {}
        if code == 0:
            ar = data.get("apply_result")
            dl = data.get("deadline_format", "n/a")
            if ar == 1:
                return "approved", f"APPROVED, unlock allowed until {dl}"
            if ar == 3:
                after_ms = (sent_at - self.midnight) * 1000
                if after_ms < self.cfg.quota_grace_ms:
                    return "retry", (f"quota-reached reply for a request sent {after_ms:+.0f} ms vs midnight, "
                                     f"treating as too early, continuing")
                return "quota", f"quota reached, try again after {dl}"
            if ar == 4:
                return "blocked", f"account blocked until {dl}"
            return "retry", f"unknown apply_result={ar} data={data}"
        if code == 100001:
            return "retry", f"rejected: {payload}"
        if code == 100003:
            return "recheck", f"maybe approved: {payload}"
        if code == 100004:
            return "expired", "cookie expired"
        return "retry", f"unknown code={code}: {payload}"

    def fire_phase(self):
        cfg = self.cfg
        method, url = ("GET", cfg.status_url) if cfg.dry_run else ("POST", cfg.apply_url)
        self.log(f"firing ({'DRY RUN, status GET' if cfg.dry_run else 'apply POST'})", BOLD + G)
        n = 0
        while not self.stopped():
            now = self.clock.now_epoch()
            if cfg.max_requests and n >= cfg.max_requests:
                self.result = f"cap of {cfg.max_requests} requests reached without a final answer"
                self.log(self.result, Y)
                return
            if cfg.stop_after_ms and (now - self.midnight) * 1000 > cfg.stop_after_ms:
                self.result = f"stop-after limit ({cfg.stop_after_ms:.0f} ms past midnight) reached"
                self.log(self.result, Y)
                return
            n += 1
            self.sent = n
            sent_at = self.clock.now_epoch()
            payload, err = do_request(self.http, method, url, self.cookie)
            recv_at = self.clock.now_epoch()
            rtt = (recv_at - sent_at) * 1000
            rel = (sent_at - self.midnight) * 1000
            if err:
                self.log(f"#{n} sent {fmt(sent_at)} ({rel:+.0f} ms) -> {err}", R)
                time.sleep(0.05)
                continue
            verdict, msg = self.classify(payload, sent_at)
            if verdict == "recheck":
                payload2, err2 = do_request(self.http, "GET", cfg.status_url, self.cookie)
                st, smsg = classify_status(payload2) if not err2 else ("none", err2)
                msg = f"{msg} | status re-check: {smsg}"
                verdict = "approved" if st == "approved" else "retry"
            color = {"approved": BOLD + G, "quota": Y, "blocked": R, "expired": R}.get(verdict, "")
            self.log(f"#{n} sent {fmt(sent_at)} ({rel:+.0f} ms) rtt {rtt:.0f} ms -> {msg}", color)
            if verdict == "approved":
                self.result = "APPROVED"
                self.stop_all.set()
                return
            if verdict in ("quota", "blocked", "expired"):
                self.result = msg
                self.stop_all.set()
                return
            time.sleep((cfg.burst_gap_ms if n < cfg.burst_count else cfg.normal_gap_ms) / 1000.0)
        if self.result == "not started":
            self.result = f"stopped after {n} request(s)"


# ----------------------------------------------------------------------------- main
def main():
    cfg = parse_args()
    cfg.test_mode = cfg.test_in_s > 0
    if cfg.test_mode:
        cfg.dry_run = True
    sys.setswitchinterval(0.001)  # let a waiting worker grab the GIL within ~1 ms

    phases = [float(x) for x in cfg.phases.split(",") if x.strip()]
    if not phases or any(ph < 0 for ph in phases):
        raise SystemExit("--phases must be a comma list of non-negative ms values")

    log_path = None if cfg.no_log else (cfg.log or f"hyperos_multi_{datetime.now():%Y%m%d_%H%M%S}.log")
    log = Log(log_path)
    hook_urllib3(log)
    log(f"hyperosunlocker_multi - {len(phases)} worker(s), phases {', '.join(f'{p:.0f}' for p in phases)} ms",
        BOLD + C)

    cfg.token = resolve_token(cfg.token, cfg.test_mode)

    servers = [s.strip() for s in cfg.ntp_servers.split(",") if s.strip()]
    clock = BeijingClock()
    log("syncing clock from NTP (lowest delay wins)", Y)
    if clock.sync(servers, cfg.ntp_samples, log) is None:
        log("primary NTP servers failed, trying fallback list", Y)
        if clock.sync(FALLBACK_NTP.split(","), cfg.ntp_samples, log) is None:
            raise SystemExit("no NTP server answered")
    log(f"clock: {clock.source} (delay {clock.delay_ms:.1f} ms), beijing now {fmt_full(clock.now_epoch())}", G)

    now = clock.now_epoch()
    if cfg.test_mode:
        midnight = now + cfg.test_in_s
        log(f"TEST MODE: pretending midnight is in {cfg.test_in_s:.0f} s ({fmt_full(midnight)}); "
            f"apply POST replaced by status GET", BOLD + Y)
    else:
        d = epoch_to_bj(now).date() + timedelta(days=1)
        midnight = BEIJING.localize(datetime(d.year, d.month, d.day)).timestamp()

    stop_all = threading.Event()
    workers = [Worker(i + 1, ph, cfg, clock, log, stop_all, midnight) for i, ph in enumerate(phases)]

    log("checking account status", Y)
    payload, err = do_request(workers[0].http, "GET", cfg.status_url, workers[0].cookie)
    state, msg = classify_status(payload) if not err else ("none", err)
    startup_gate(state, msg, log, cfg.test_mode)

    log("plan:", BOLD)
    log(f"  midnight (target)   {fmt_full(midnight)}, in {midnight - clock.now_epoch():.0f} s")
    for w in workers:
        log(f"  {w.tag.strip():<14} fires at {fmt(w.fire_at)}")
    log(f"  per worker: burst {cfg.burst_count} @ {cfg.burst_gap_ms:.0f} ms, then every {cfg.normal_gap_ms:.0f} ms; "
        f"cap {cfg.max_requests or 'none'}; stop {cfg.stop_after_ms:.0f} ms after midnight")
    log(f"  keep-alive every {cfg.keepalive_s:.0f} s, final warm-up {cfg.final_warm_ms:.0f} ms before firing, "
        f"NTP re-sync {cfg.resync_s:.0f} s before midnight")
    if cfg.dry_run and not cfg.test_mode:
        log("DRY RUN: apply POST replaced by status GET", BOLD + Y)
    log("do not close this window. Ctrl+C stops all workers.", Y)

    for w in workers:
        w.start()

    resync_at = None
    if cfg.resync_s > 0 and (midnight - clock.now_epoch()) > cfg.resync_s + 10:
        resync_at = midnight - cfg.resync_s
    try:
        while any(w.is_alive() for w in workers):
            if resync_at is not None and clock.now_epoch() >= resync_at:
                resync_at = None
                jump = clock.sync(servers, cfg.ntp_samples, log)
                if jump is None:
                    log("re-sync failed, keeping the earlier reference", Y)
                else:
                    log(f"re-sync via {clock.source} (delay {clock.delay_ms:.1f} ms): clock adjusted by {jump:+.1f} ms", G)
            time.sleep(0.2)
    except KeyboardInterrupt:
        log("Ctrl+C, stopping all workers", R)
        stop_all.set()
        for w in workers:
            w.join(timeout=3)

    log("summary:", BOLD)
    for w in workers:
        log(f"  {w.tag.strip():<14} {w.sent} request(s): {w.result}", BOLD + G if w.result == "APPROVED" else "")
    if not cfg.test_mode:
        payload, err = do_request(workers[0].http, "GET", cfg.status_url, workers[0].cookie)
        state, msg = classify_status(payload) if not err else ("none", err)
        log(f"final account status: {msg}", BOLD + G if state == "approved" else Y)
    log("on the phone now, whatever the result: sign out of the Mi account, reboot, sign in, "
        "Developer options > Mi Unlock status > Add account and device, enable OEM unlocking, then check Mi Unlock.", C)
    if log_path:
        log(f"log written to {log_path}")


if __name__ == "__main__":
    main()
