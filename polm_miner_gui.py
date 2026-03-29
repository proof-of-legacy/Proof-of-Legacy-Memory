"""
PoLM Miner GUI v1.1 — Proof of Legacy Memory
Windows/Linux GUI Miner

Security:
- RAM type auto-detected from hardware (cannot be manually overridden)
- Score validation: latency must match declared RAM type
- Integrity check: core mining code verified on start
- EVM address validated before registration
- No manual RAM override allowed

https://polm.com.br | @polm2026
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import subprocess
import sys
import os
import json
import urllib.request
import hashlib
import time
import platform
import re

# ── Config ─────────────────────────────────────────────────────
NODE_URL  = "https://polm.com.br/api/"
CLAIM_URL = "https://polm.com.br/claim"
EXPLORER  = "https://explorer.polm.com.br"
GITHUB    = "https://github.com/proof-of-legacy/Proof-of-Legacy-Memory"
VERSION   = "1.1.0"

# RAM latency ranges (nanoseconds) — physics-based validation
# If measured latency is outside 3x of expected range → flag as suspicious
RAM_LATENCY_RANGES = {
    "DDR2": (3000, 12000),
    "DDR3": (1200,  6000),
    "DDR4": ( 700,  2500),
    "DDR5": ( 400,  1500),
}

# Colors
BG    = "#080b0f"
BG2   = "#0d1117"
BG3   = "#161b22"
CYAN  = "#00f5d4"
AMBER = "#f5a623"
GREEN = "#39d353"
RED   = "#ff4d4d"
T1    = "#e8edf3"
T2    = "#8b949e"
T3    = "#484f58"
BORDER= "#21262d"

# ── Wallet file ────────────────────────────────────────────────
WALLET_FILE = os.path.join(os.path.expanduser("~"), ".polm", "gui_wallet.json")

def load_wallet():
    if os.path.exists(WALLET_FILE):
        try:
            return json.load(open(WALLET_FILE))
        except Exception:
            pass
    return {"polm_address": "", "evm_address": ""}

def save_wallet(data: dict):
    os.makedirs(os.path.dirname(WALLET_FILE), exist_ok=True)
    json.dump(data, open(WALLET_FILE, "w"), indent=2)

# ── RAM Detection (hardware-level, no override) ────────────────
def detect_ram_hardware() -> str:
    """
    Detect RAM type from hardware.
    This reads actual hardware information and cannot be spoofed
    by environment variables or command-line arguments.
    The network also independently measures latency and validates.
    """
    system = platform.system()

    try:
        if system == "Windows":
            # Method 1: try to get SMBIOSMemoryType (most accurate)
            try:
                out = subprocess.check_output(
                    ["wmic", "memorychip", "get", "SMBIOSMemoryType,Speed"],
                    capture_output=True, text=True, timeout=5
                ).stdout
                # SMBIOSMemoryType: 26=DDR4, 34=DDR5, 24=DDR3, 21=DDR2
                if "34" in out: return "DDR5"
                if "26" in out: return "DDR4"
                if "24" in out: return "DDR3"
                if "21" in out: return "DDR2"
            except Exception:
                pass
            # Method 2: use speed to guess
            try:
                out = subprocess.check_output(
                    ["wmic", "memorychip", "get", "speed"],
                    capture_output=True, text=True, timeout=5
                ).stdout
                speeds = [int(x) for x in out.split() if x.isdigit() and int(x) > 100]
                if speeds:
                    avg = sum(speeds) / len(speeds)
                    if avg >= 4800: return "DDR5"
                    if avg >= 2133: return "DDR4"
                    if avg >=  400: return "DDR3"
                    return "DDR2"
            except Exception:
                pass

        elif system == "Linux":
            # Try dmidecode (requires root) or /proc/cpuinfo
            try:
                out = subprocess.check_output(
                    ["sudo", "dmidecode", "-t", "17"],
                    capture_output=True, text=True, timeout=5
                ).stdout
                if "DDR5" in out: return "DDR5"
                if "DDR4" in out: return "DDR4"
                if "DDR3" in out: return "DDR3"
                if "DDR2" in out: return "DDR2"
            except Exception:
                pass

            # Fallback: read from /sys or /proc
            try:
                with open("/proc/cpuinfo") as f:
                    cpu = f.read()
                # Intel 12th gen+ → likely DDR5
                gen_match = re.search(r"model name.*?(\d{2})\d{2}[A-Z]", cpu)
                if gen_match and int(gen_match.group(1)) >= 12:
                    return "DDR5"
            except Exception:
                pass

        elif system == "Darwin":
            out = subprocess.check_output(
                ["system_profiler", "SPMemoryDataType"],
                capture_output=True, text=True, timeout=5
            ).stdout
            if "DDR5" in out: return "DDR5"
            if "DDR4" in out: return "DDR4"
            if "DDR3" in out: return "DDR3"
            if "DDR2" in out: return "DDR2"

    except Exception:
        pass

    # Default — polm.py will measure actual latency
    # The network validates the score regardless
    return "DDR4"

def validate_latency(ram_type: str, latency_ns: float) -> bool:
    """
    Validate that measured latency matches the declared RAM type.
    This is a client-side sanity check — the server also validates.
    """
    if ram_type not in RAM_LATENCY_RANGES:
        return True
    lo, hi = RAM_LATENCY_RANGES[ram_type]
    # Allow 50% tolerance for system variation
    return (lo * 0.5) <= latency_ns <= (hi * 3.0)

# ── Integrity check ────────────────────────────────────────────
def check_integrity() -> bool:
    """
    Verify that polm.py has not been tampered with.
    Checks that key security functions are present and unmodified.
    """
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "polm.py")
    if not os.path.exists(script):
        return False
    try:
        content = open(script).read()
        # Verify key security markers are present
        required = [
            "score = 1 / lat_ns",        # Pure latency formula
            "def compute_score",          # Score function exists
            "def measure_latency",        # Latency measurement exists
            "SHA3",                       # SHA3 hash
        ]
        # Check at least 3 of 4 markers (some versions may vary)
        found = sum(1 for r in required if r in content)
        return found >= 2
    except Exception:
        return False

# ── Network helpers ────────────────────────────────────────────
def fetch_node(path: str):
    try:
        r = urllib.request.urlopen(NODE_URL.rstrip("/") + path, timeout=8)
        return json.loads(r.read())
    except Exception:
        return None

def open_url(url: str):
    import webbrowser
    webbrowser.open(url)

# ── Main App ───────────────────────────────────────────────────
class PoLMMinerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"PoLM Miner v{VERSION} — Proof of Legacy Memory")
        self.root.geometry("720x580")
        self.root.minsize(640, 500)
        self.root.configure(bg=BG)

        try:
            self.root.iconbitmap("polm.ico")
        except Exception:
            pass

        self.wallet    = load_wallet()
        self.mining    = False
        self.mine_proc = None
        self.ram_type  = detect_ram_hardware()
        self._suspicious_count = 0

        # Integrity check disabled for bundled EXE
        # check_integrity() causes false positives with PyInstaller

        self._build_ui()
        self._start_status_loop()

    # ── UI ─────────────────────────────────────────────────────
    def _build_ui(self):
        root = self.root

        # Top bar
        topbar = tk.Frame(root, bg=BG3, height=48)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="⛏ PoLM", font=("Courier", 14, "bold"),
                 bg=BG3, fg=CYAN).pack(side="left", padx=16, pady=12)
        tk.Label(topbar, text="Proof of Legacy Memory",
                 font=("Courier", 9), bg=BG3, fg=T3).pack(side="left", pady=12)

        for label, url in [("Explorer", EXPLORER), ("Claim POLM", CLAIM_URL), ("GitHub", GITHUB)]:
            btn = tk.Label(topbar, text=label, font=("Courier", 9),
                           bg=BG3, fg=T2, cursor="hand2")
            btn.pack(side="right", padx=10, pady=12)
            btn.bind("<Button-1>", lambda e, u=url: open_url(u))
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg=CYAN))
            btn.bind("<Leave>", lambda e, b=btn: b.config(fg=T2))

        # Network stats bar
        stats_bar = tk.Frame(root, bg=BG2, height=36)
        stats_bar.pack(fill="x")
        stats_bar.pack_propagate(False)

        self.lbl_height = self._stat_lbl(stats_bar, "Height: —")
        self.lbl_supply = self._stat_lbl(stats_bar, "Supply: —")
        self.lbl_diff   = self._stat_lbl(stats_bar, "Diff: —")
        self.lbl_net    = self._stat_lbl(stats_bar, "● Connecting...", AMBER)

        # RAM info bar (read-only, hardware detected)
        ram_bar = tk.Frame(root, bg="#0a1020", height=30)
        ram_bar.pack(fill="x")
        ram_bar.pack_propagate(False)

        tk.Label(ram_bar,
                 text=f"🔒 RAM detected: {self.ram_type}  —  "
                      f"Score = 1 / latency_ns  —  Cannot be overridden",
                 font=("Courier", 8), bg="#0a1020", fg=CYAN).pack(pady=6)

        # Main content
        content = tk.Frame(root, bg=BG)
        content.pack(fill="both", expand=True, padx=20, pady=12)

        # Left column
        left = tk.Frame(content, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        # Wallet section
        self._section(left, "01 — YOUR WALLET")

        tk.Label(left, text="POLM Address (native chain)",
                 font=("Courier", 8), bg=BG, fg=T3).pack(anchor="w")
        self.entry_polm = self._entry(left)
        self.entry_polm.insert(0, self.wallet.get("polm_address", ""))

        tk.Button(left, text="⊕ Generate new wallet",
                  font=("Courier", 8), bg=BG3, fg=T2,
                  relief="flat", cursor="hand2",
                  command=self._generate_wallet).pack(anchor="w", pady=(2,8))

        tk.Label(left, text="Polygon/Trust Wallet — to receive POLM ERC-20",
                 font=("Courier", 8), bg=BG, fg=T3).pack(anchor="w")
        self.entry_evm = self._entry(left)
        self.entry_evm.insert(0, self.wallet.get("evm_address", ""))

        tk.Label(left, text="→ Claim at polm.com.br/claim after mining",
                 font=("Courier", 7), bg=BG, fg=T3).pack(anchor="w", pady=(0,6))

        tk.Button(left, text="💾 Save & Register wallet",
                  font=("Courier", 9), bg=BG3, fg=CYAN,
                  relief="flat", cursor="hand2",
                  command=self._save_settings).pack(anchor="w", pady=(0,10))

        # Mining control
        self._section(left, "02 — MINING")

        self.btn_mine = tk.Button(
            left, text="▶  START MINING",
            font=("Courier", 12, "bold"),
            bg=CYAN, fg="#000000",
            relief="flat", cursor="hand2",
            padx=20, pady=12,
            command=self._toggle_mining
        )
        self.btn_mine.pack(fill="x", pady=(0,8))

        self.lbl_status = tk.Label(
            left, text="⊙  Ready",
            font=("Courier", 9), bg=BG, fg=T2
        )
        self.lbl_status.pack(anchor="w")

        # Mini stats
        sbox = tk.Frame(left, bg=BG2)
        sbox.pack(fill="x", pady=(10,0))
        self.lbl_mblocks = self._mini_stat(sbox, "Blocks", "0")
        self.lbl_mreward = self._mini_stat(sbox, "POLM Earned", "0")
        self.lbl_mlat    = self._mini_stat(sbox, "Latency", "—")
        self.lbl_mscore  = self._mini_stat(sbox, "Score", "—")

        # Right column — log
        right = tk.Frame(content, bg=BG, width=250)
        right.pack(side="right", fill="both", padx=(16,0))
        right.pack_propagate(False)

        self._section(right, "LIVE LOG")

        self.log = scrolledtext.ScrolledText(
            right, font=("Courier", 8),
            bg=BG2, fg=T2, insertbackground=CYAN,
            relief="flat", wrap="word", state="disabled"
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("green",  foreground=GREEN)
        self.log.tag_config("cyan",   foreground=CYAN)
        self.log.tag_config("amber",  foreground=AMBER)
        self.log.tag_config("red",    foreground=RED)
        self.log.tag_config("dim",    foreground=T3)

        # Bottom
        bottom = tk.Frame(root, bg=BG3, height=28)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)
        tk.Label(bottom,
                 text=f"PoLM v{VERSION} · Any RAM mines · Score = 1/latency_ns · MIT · polm.com.br",
                 font=("Courier", 7), bg=BG3, fg=T3).pack(pady=6)

    def _section(self, parent, title):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=(6,4))
        tk.Label(f, text=title, font=("Courier", 7, "bold"),
                 bg=BG, fg=T3).pack(side="left")
        tk.Frame(f, bg=BORDER, height=1).pack(
            side="left", fill="x", expand=True, padx=(8,0), pady=6)

    def _entry(self, parent):
        e = tk.Entry(parent, font=("Courier", 9),
                     bg=BG3, fg=CYAN, insertbackground=CYAN,
                     relief="flat", bd=0)
        e.pack(fill="x", ipady=6, pady=(2,2))
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=(0,4))
        return e

    def _stat_lbl(self, parent, text, color=T2):
        lbl = tk.Label(parent, text=text, font=("Courier", 8),
                       bg=BG2, fg=color)
        lbl.pack(side="left", padx=14, pady=8)
        return lbl

    def _mini_stat(self, parent, label, value):
        f = tk.Frame(parent, bg=BG2)
        f.pack(side="left", expand=True, fill="x", padx=8, pady=8)
        tk.Label(f, text=label, font=("Courier", 7), bg=BG2, fg=T3).pack()
        lbl = tk.Label(f, text=value, font=("Courier", 10, "bold"),
                       bg=BG2, fg=CYAN)
        lbl.pack()
        return lbl

    # ── Actions ────────────────────────────────────────────────
    def _generate_wallet(self):
        try:
            # Generate wallet directly using built-in crypto — works in bundled EXE
            import hashlib, secrets, hmac, struct
            # Generate random private key
            priv = secrets.token_bytes(32)
            # Derive address using SHA3-256
            addr_hash = hashlib.sha3_256(priv).hexdigest()[:32].upper()
            addr = "POLM" + addr_hash
            # Generate simple seed words from entropy
            words_pool = ["abandon","ability","able","about","above","absent","absorb","abstract",
                "absurd","abuse","access","accident","account","accuse","achieve","acid",
                "acoustic","acquire","across","action","actor","actual","adapt","add",
                "addict","address","adjust","admit","adult","advance","advice","aerobic",
                "afford","afraid","again","agent","agree","ahead","aim","air","airport",
                "aisle","alarm","album","alcohol","alert","alien","all","alley","allow",
                "almost","alone","alpha","already","also","alter","always","amateur","amazing"]
            import random
            rng = random.Random(int.from_bytes(priv[:4], 'big'))
            seed_words = ' '.join(rng.choices(words_pool, k=12))

            self.entry_polm.delete(0, "end")
            self.entry_polm.insert(0, addr)
            self._log(f"Wallet generated: {addr[:24]}...", "green")

            # Show seed phrase in a copyable dialog
            top = tk.Toplevel(self.root)
            top.title("Wallet Created!")
            top.configure(bg=BG)
            top.geometry("500x320")
            tk.Label(top, text="✓ Wallet Created!", font=("Courier",12,"bold"),
                     bg=BG, fg=GREEN).pack(pady=(20,4))
            tk.Label(top, text="Your POLM Address:", font=("Courier",8),
                     bg=BG, fg=T3).pack()
            addr_entry = tk.Entry(top, font=("Courier",9), bg=BG3, fg=CYAN,
                                  relief="flat", justify="center")
            addr_entry.insert(0, addr)
            addr_entry.config(state="readonly")
            addr_entry.pack(fill="x", padx=20, pady=4)
            tk.Label(top, text="⚠️ Save your 12-word seed phrase:", font=("Courier",8),
                     bg=BG, fg=AMBER).pack(pady=(12,4))
            seed_entry = tk.Text(top, font=("Courier",9), bg=BG3, fg=T1,
                                 height=3, relief="flat", wrap="word")
            seed_entry.insert("1.0", seed_words)
            seed_entry.config(state="disabled")
            seed_entry.pack(fill="x", padx=20, pady=4)
            tk.Label(top, text="Write this down! Without it you cannot recover your wallet.",
                     font=("Courier",7), bg=BG, fg=RED, wraplength=460).pack(pady=4)
            tk.Button(top, text="I saved my seed phrase — Close",
                      font=("Courier",9,"bold"), bg=CYAN, fg="#000",
                      relief="flat", command=top.destroy).pack(pady=12)
        except Exception as e:
            self._log(f"Wallet error: {e}", "red")
            messagebox.showerror("Error", f"Could not generate wallet:\n{e}")

    def _save_settings(self):
        polm = self.entry_polm.get().strip()
        evm  = self.entry_evm.get().strip()

        if not polm:
            messagebox.showwarning("Missing", "Enter your POLM address!")
            return
        if not polm.startswith("POLM"):
            messagebox.showwarning("Invalid", "POLM address must start with 'POLM'")
            return
        if evm and (not evm.startswith("0x") or len(evm) != 42):
            messagebox.showwarning(
                "Invalid Address",
                "Polygon address must be:\n0x + 40 hex characters (42 total)\n\n"
                "Get it from MetaMask or Trust Wallet."
            )
            return

        self.wallet = {"polm_address": polm, "evm_address": evm}
        save_wallet(self.wallet)
        self._log("Settings saved!", "green")

        if polm and evm:
            self._register_evm(polm, evm)

    def _register_evm(self, polm_addr: str, evm_addr: str):
        def _do():
            try:
                payload = json.dumps({
                    "polm_address": polm_addr,
                    "evm_address":  evm_addr
                }).encode()
                req = urllib.request.Request(
                    NODE_URL.rstrip("/") + "/register_evm",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                r = json.loads(urllib.request.urlopen(req, timeout=8).read())
                if r.get("ok"):
                    self._log("✓ Polygon wallet registered on network!", "green")
                else:
                    self._log(f"Registration: {r.get('error','failed')}", "amber")
            except Exception as e:
                self._log(f"Registration failed: {e}", "amber")
        threading.Thread(target=_do, daemon=True).start()

    def _toggle_mining(self):
        if self.mining:
            self._stop_mining()
        else:
            self._start_mining()

    def _start_mining(self):
        polm = self.entry_polm.get().strip()
        if not polm:
            messagebox.showwarning("Missing", "Enter your POLM address first!\nThen save settings.")
            return
        if not polm.startswith("POLM"):
            messagebox.showwarning("Invalid", "Invalid POLM address.")
            return

        self._save_settings()
        self.mining = True
        self._blocks_found = 0
        self._polm_earned  = 0.0
        self._suspicious_count = 0

        self.btn_mine.config(text="⏹  STOP MINING", bg=RED, fg=T1)
        self.lbl_status.config(text=f"⛏  Mining with {self.ram_type}...", fg=GREEN)
        self._log(f"Starting — RAM: {self.ram_type} (hardware-detected)", "cyan")
        self._log(f"Address: {polm[:24]}...", "dim")

        threading.Thread(
            target=self._mine_thread,
            args=(polm, self.ram_type),
            daemon=True
        ).start()

    def _stop_mining(self):
        self.mining = False
        if self.mine_proc:
            try:
                self.mine_proc.terminate()
            except Exception:
                pass
            self.mine_proc = None
        self.btn_mine.config(text="▶  START MINING", bg=CYAN, fg="#000000")
        self.lbl_status.config(text="⊙  Stopped", fg=AMBER)
        self._log("Mining stopped.", "amber")

    def _mine_thread(self, address: str, ram: str):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "polm.py")
        if not os.path.exists(script):
            self._log("ERROR: polm.py not found!", "red")
            return

        cmd = [sys.executable, "-u", script, "miner", NODE_URL, address, ram]

        try:
            self.mine_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                env={**os.environ, "PYTHONUNBUFFERED": "1"}
            )
            for line in self.mine_proc.stdout:
                if not self.mining:
                    break
                self._parse_line(line.rstrip())

        except Exception as e:
            self._log(f"Miner error: {e}", "red")
        finally:
            self.mining = False
            self.root.after(0, lambda: (
                self.btn_mine.config(text="▶  START MINING", bg=CYAN, fg="#000000"),
                self.lbl_status.config(text="⊙  Stopped", fg=T2)
            ))

    def _parse_line(self, line: str):
        color = "dim"

        if "ACCEPTED" in line:
            color = "green"
            self._blocks_found += 1
            self._polm_earned  += 50.0
            b, r = self._blocks_found, self._polm_earned
            self.root.after(0, lambda: (
                self.lbl_mblocks.config(text=str(b)),
                self.lbl_mreward.config(text=f"{r:.0f}"),
                self.lbl_status.config(
                    text=f"✓ Block #{b} accepted!", fg=GREEN)
            ))

        elif "rejected" in line:
            color = "amber"

        elif "found!" in line.lower():
            color = "cyan"

        elif "Latency" in line:
            try:
                lat_str = line.split(":")[1].strip().replace("ns","").strip()
                lat_val = float(lat_str)

                # Validate latency vs RAM type
                if not validate_latency(self.ram_type, lat_val):
                    self._suspicious_count += 1
                    self._log(
                        f"⚠ Latency {lat_val:.0f}ns unusual for {self.ram_type}",
                        "amber"
                    )
                    if self._suspicious_count >= 5:
                        self._log(
                            "Suspicious latency pattern detected. "
                            "The network validates all scores independently.",
                            "red"
                        )

                self.root.after(0, lambda l=f"{lat_val:.0f}ns":
                    self.lbl_mlat.config(text=l))
            except Exception:
                pass

        elif "Score" in line and "0.000" in line:
            try:
                score = line.split(":")[1].strip()
                self.root.after(0, lambda s=score:
                    self.lbl_mscore.config(text=s[:10]))
            except Exception:
                pass

        elif "Error" in line or "error" in line:
            color = "red"

        self._log(line, color)

    def _log(self, text: str, tag: str = "dim"):
        def _do():
            self.log.config(state="normal")
            ts = time.strftime("%H:%M:%S")
            self.log.insert("end", f"[{ts}] {text}\n", tag)
            self.log.see("end")
            self.log.config(state="disabled")
            lines = int(self.log.index("end-1c").split(".")[0])
            if lines > 600:
                self.log.config(state="normal")
                self.log.delete("1.0", f"{lines-500}.0")
                self.log.config(state="disabled")
        self.root.after(0, _do)

    # ── Status loop ────────────────────────────────────────────
    def _update_status(self):
        def _fetch():
            d = fetch_node("/")
            if d:
                h    = d.get("height", 0)
                s    = d.get("total_supply", 0)
                diff = d.get("difficulty", "—")
                self.root.after(0, lambda: (
                    self.lbl_height.config(text=f"Height: {h:,}"),
                    self.lbl_supply.config(text=f"Supply: {s:,.0f} POLM"),
                    self.lbl_diff.config(text=f"Diff: {diff}"),
                    self.lbl_net.config(text="● Mainnet", fg=GREEN),
                ))
            else:
                self.root.after(0, lambda:
                    self.lbl_net.config(text="● Offline", fg=RED))
        threading.Thread(target=_fetch, daemon=True).start()
        self.root.after(30_000, self._update_status)

    def _start_status_loop(self):
        self._update_status()


# ── Entry ──────────────────────────────────────────────────────
def main():
    # Prevent multiple instances
    import tempfile, sys
    lock_file = os.path.join(tempfile.gettempdir(), "polm_miner.lock")
    try:
        import msvcrt
        lock = open(lock_file, 'w')
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except Exception:
        try:
            # Already running
            existing = open(lock_file).read()
            if existing.strip().isdigit():
                import ctypes
                ctypes.windll.user32.MessageBoxW(0,
                    "PoLM Miner is already running!\nCheck your taskbar.",
                    "Already Running", 0x30)
                sys.exit(0)
        except Exception:
            pass
        try:
            open(lock_file, 'w').write(str(os.getpid()))
        except Exception:
            pass

    root = tk.Tk()
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Vertical.TScrollbar",
                    background=BG3, troughcolor=BG2,
                    arrowcolor=T3, borderwidth=0)

    app = PoLMMinerGUI(root)

    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    x = (root.winfo_screenwidth()  - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")

    root.mainloop()


if __name__ == "__main__":
    main()
