#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Wi‑Fi Keep‑Alive with a tiny Tkinter UI

Features
--------
* Starts / stops the keep‑alive loop with a button.
* Shows real‑time log output inside the window.
* Allows you to edit the key parameters (URL, interval, time‑outs) via the UI
  and persist them to keepalive_config.json.
* Falls back to built‑in defaults if the JSON file is missing.
* Works on any Windows machine with Python 3.8+ (standard library only).

Author: Crema 2.5 – Styrite
"""

import sys
import json
import time
import socket
import subprocess
import threading
import traceback
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import urllib.parse
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# ----------------------------------------------------------------------
# Paths & default configuration -----------------------------------------
# ----------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "keepalive_config.json"

DEFAULT_CFG = {
    "keep_alive_url": "https://www.gstatic.com/generate_204",
    "interval": 30,
    "log_file": None,
    "timeout": 10,
    "dns_timeout": 5,
}


def load_config() -> dict:
    """Read keepalive_config.json if it exists; otherwise return defaults."""
    cfg = DEFAULT_CFG.copy()
    if CONFIG_PATH.is_file():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception as exc:
            log(f"⚠️  Failed to read config file: {exc}")
    return cfg


def save_config(cfg: dict) -> None:
    """Write the current config back to keepalive_config.json (pretty‑printed)."""
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, indent=4, ensure_ascii=False), encoding="utf-8")
        log("💾 Configuration saved.")
    except Exception as exc:
        log(f"❌ Could not write config file: {exc}")


# ----------------------------------------------------------------------
# Logging helper --------------------------------------------------------
# ----------------------------------------------------------------------
log_lock = threading.Lock()


def log(message: str) -> None:
    """Thread‑safe timestamped logging – prints to console and UI (if present)."""
    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    line = f"[{timestamp}] {message}"
    with log_lock:
        print(line)
        # If the UI has been created, forward the line to the ScrolledText widget.
        if hasattr(log, "ui_text"):
            log.ui_text.configure(state="normal")
            log.ui_text.insert(tk.END, line + "\n")
            log.ui_text.see(tk.END)
            log.ui_text.configure(state="disabled")


# ----------------------------------------------------------------------
# Network utilities ------------------------------------------------------
# ----------------------------------------------------------------------
def get_active_wifi_interface() -> str | None:
    """Uses `netsh wlan show interfaces` to locate a connected Wi‑Fi adapter."""
    try:
        out = subprocess.check_output(
            ["netsh", "wlan", "show", "interfaces"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except Exception:
        return None

    iface = None
    for line in out.splitlines():
        if line.strip().startswith("Name"):
            iface = line.split(":", 1)[1].strip()
        if line.strip().startswith("State"):
            state = line.split(":", 1)[1].strip().lower()
            if state != "connected":
                iface = None
        if line.strip().startswith("IPv4 Address"):
            if iface:
                return iface
    return None


def resolve_host(host: str, timeout: int) -> tuple[bool, float, list[str]]:
    """Manual DNS lookup so we can log latency."""
    start = time.time()
    try:
        addrinfo = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        ips = list({info[4][0] for info in addrinfo})
        elapsed = time.time() - start
        return True, elapsed, ips
    except socket.gaierror as e:
        elapsed = time.time() - start
        log(f"❌ DNS error for {host}: {e}")
        return False, elapsed, []


def keepalive_request(url: str, timeout: int, dns_timeout: int) -> bool:
    """Send a single HEAD request and return True on a 2xx/3xx response."""
    try:
        parsed = urllib.parse.urlparse(url)
        ok, dns_ms, ips = resolve_host(parsed.hostname, dns_timeout)
        if not ok:
            log("⚠️  Skipping request because DNS failed.")
            return False
        log(f"🔎 DNS resolved {parsed.hostname} → {', '.join(ips)} in {dns_ms*1000:.0f} ms")

        req = Request(url, method="HEAD")
        with urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            log(f"📡 Received HTTP {code} from {url}")
            return 200 <= code < 400
    except Exception as exc:
        log(f"❗ Request exception: {exc}")
        return False


# ----------------------------------------------------------------------
# Worker thread – runs the periodic keep‑alive -------------------------
# ----------------------------------------------------------------------
class KeepAliveWorker(threading.Thread):
    def __init__(self, cfg: dict, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.stop_event = stop_event

    def run(self) -> None:
        log("🚀 Keep‑alive thread started.")
        while not self.stop_event.is_set():
            # Verify Wi‑Fi is still present; abort loop if it disappears.
            if not get_active_wifi_interface():
                log("⚠️  Wi‑Fi interface disappeared – stopping thread.")
                break

            success = keepalive_request(
                self.cfg["keep_alive_url"],
                self.cfg["timeout"],
                self.cfg["dns_timeout"],
            )
            log("✅ Ping succeeded." if success else "❌ Ping failed.")
            # Wait for the interval or an early stop request.
            stopped = self.stop_event.wait(self.cfg["interval"])
            if stopped:
                break
        log("🛑 Keep‑alive thread terminated.")


# ----------------------------------------------------------------------
# Tkinter UI ------------------------------------------------------------
# ----------------------------------------------------------------------
class KeepAliveApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Wi‑Fi Keep‑Alive")
        self.resizable(False, False)

        # Load (or create) configuration.
        self.cfg = load_config()

        # UI elements ---------------------------------------------------
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="NSEW")

        # URL entry
        ttk.Label(main_frame, text="Keep‑Alive URL:").grid(row=0, column=0, sticky="W")
        self.url_var = tk.StringVar(value=self.cfg["keep_alive_url"])
        ttk.Entry(main_frame, width=50, textvariable=self.url_var).grid(
            row=0, column=1, columnspan=2, pady=2, sticky="W"
        )

        # Interval
        ttk.Label(main_frame, text="Interval (seconds):").grid(row=1, column=0, sticky="W")
        self.interval_var = tk.IntVar(value=self.cfg["interval"])
        ttk.Spinbox(
            main_frame, from_=5, to=3600, increment=5, textvariable=self.interval_var, width=10
        ).grid(row=1, column=1, sticky="W", pady=2)

        # Timeout
        ttk.Label(main_frame, text="Request timeout (s):").grid(row=2, column=0, sticky="W")
        self.timeout_var = tk.IntVar(value=self.cfg["timeout"])
        ttk.Spinbox(
            main_frame, from_=1, to=60, increment=1, textvariable=self.timeout_var, width=10
        ).grid(row=2, column=1, sticky="W", pady=2)

        # DNS timeout
        ttk.Label(main_frame, text="DNS timeout (s):").grid(row=3, column=0, sticky="W")
        self.dns_timeout_var = tk.IntVar(value=self.cfg["dns_timeout"])
        ttk.Spinbox(
            main_frame, from_=1, to=30, increment=1, textvariable=self.dns_timeout_var, width=10
        ).grid(row=3, column=1, sticky="W", pady=2)

        # Log file (optional)
        ttk.Label(main_frame, text="Log file (optional):").grid(row=4, column=0, sticky="W")
        self.logfile_var = tk.StringVar(value=self.cfg["log_file"] or "")
        ttk.Entry(main_frame, width=40, textvariable=self.logfile_var).grid(
            row=4, column=1, columnspan=2, sticky="W", pady=2
        )

        # Buttons --------------------------------------------------------
        self.start_btn = ttk.Button(main_frame, text="Start", command=self.start_keepalive)
        self.start_btn.grid(row=5, column=0, pady=8, sticky="W")

        self.stop_btn = ttk.Button(main_frame, text="Stop", command=self.stop_keepalive, state="disabled")
        self.stop_btn.grid(row=5, column=1, pady=8, sticky="W")

        ttk.Button(main_frame, text="Save Settings", command=self.save_settings).grid(
            row=5, column=2, pady=8, sticky="E"
        )

        # Log view -------------------------------------------------------
        ttk.Label(main_frame, text="Log output:").grid(row=6, column=0, columnspan=3, sticky="W")
        self.log_text = scrolledtext.ScrolledText(main_frame, width=70, height=15, state="disabled")
        self.log_text.grid(row=7, column=0, columnspan=3, pady=4)

        # Bind the logger to the UI widget.
        log.ui_text = self.log_text

        # Thread control
        self.stop_event = threading.Event()
        self.worker: KeepAliveWorker | None = None

        # Graceful shutdown handling
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------------
    def start_keepalive(self):
        """Kick off the background thread."""
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Info", "Keep‑alive is already running.")
            return

        # Apply UI fields to the runtime config before starting.
        self.cfg["keep_alive_url"] = self.url_var.get().strip()
        self.cfg["interval"] = max(5, self.interval_var.get())
        self.cfg["timeout"] = max(1, self.timeout_var.get())
        self.cfg["dns_timeout"] = max(1, self.dns_timeout_var.get())
        self.cfg["log_file"] = self.logfile_var.get().strip() or None

        self.stop_event.clear()
        self.worker = KeepAliveWorker(self.cfg, self.stop_event)
        self.worker.start()

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        log("▶️ Keep‑alive started from UI.")

    # ------------------------------------------------------------------
    def stop_keepalive(self):
        """Signal the thread to stop."""
        if self.worker and self.worker.is_alive():
            self.stop_event.set()
            self.worker.join(timeout=5)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        log("⏸️ Keep‑alive stopped from UI.")

    # ------------------------------------------------------------------
    def save_settings(self):
        """Persist the current UI fields to keepalive_config.json."""
        self.cfg["keep_alive_url"] = self.url_var.get().strip()
        self.cfg["interval"] = max(5, self.interval_var.get())
        self.cfg["timeout"] = max(1, self.timeout_var.get())
        self.cfg["dns_timeout"] = max(1, self.dns_timeout_var.get())
        self.cfg["log_file"] = self.logfile_var.get().strip() or None
        save_config(self.cfg)

    # ------------------------------------------------------------------
    def on_close(self):
        """Make sure the background thread shuts down before the process exits."""
        self.stop_keepalive()
        self.destroy()


if __name__ == "__main__":
    # Force line‑buffered stdout (helpful when piping logs).
    sys.stdout = open(
        sys.stdout.fileno(),
        mode="w",
        buffering=1,
        encoding="utf-8",
        newline="\n",
    )
    app = KeepAliveApp()
    app.mainloop()
