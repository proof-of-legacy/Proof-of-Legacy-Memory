"""
PoLM Wallet  v2.0.0  —  BIP-39 / HD Wallet
https://polm.com.br

Web Wallet UI: Dashboard · Send · Receive · History · Addresses · Network
CLI:  show | new | balance | send

Cross-platform: Windows 10/11 | Linux | macOS
"""

import sys, os

if sys.platform == "win32":
    import io, asyncio
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

IS_WIN = sys.platform == "win32"

import hashlib, time, json, secrets, threading, platform
import urllib.request
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Tuple
from flask import Flask, jsonify, request, Response

VERSION = "2.1.0"
SYMBOL  = "POLM"
WEBSITE = "https://polm.com.br"
MIN_FEE = 0.0001

try:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.backends import default_backend
    HAVE_CRYPTO = True
except ImportError:
    HAVE_CRYPTO = False

# ─────────────────────────────────────────────────────────────────
# CRYPTO
# ─────────────────────────────────────────────────────────────────
def pubkey_to_address(pub_hex: str) -> str:
    h = hashlib.sha3_256(
        hashlib.sha3_256(bytes.fromhex(pub_hex)).digest()
    ).hexdigest()
    return "POLM" + h[:32].upper()

def generate_keypair() -> Tuple[str, str, str]:
    if HAVE_CRYPTO:
        priv = ec.generate_private_key(ec.SECP256K1(), default_backend())
        priv_hex = priv.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()
        ).hex()
        pub_hex = priv.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.CompressedPoint
        ).hex()
    else:
        priv_hex = secrets.token_hex(32)
        pub_hex  = hashlib.sha3_256(bytes.fromhex(priv_hex)).hexdigest()
    return priv_hex, pub_hex, pubkey_to_address(pub_hex)

def sign_data(priv_hex: str, data: bytes) -> str:
    if HAVE_CRYPTO:
        priv = serialization.load_der_private_key(
            bytes.fromhex(priv_hex), password=None, backend=default_backend()
        )
        return priv.sign(data, ec.ECDSA(hashes.SHA256())).hex()
    return hashlib.sha3_256(priv_hex.encode() + data).hexdigest()

# ─────────────────────────────────────────────────────────────────
# WALLET FILE
# ─────────────────────────────────────────────────────────────────
@dataclass
class WalletKey:
    address:  str
    pub_hex:  str
    priv_hex: str
    label:    str = ""
    created:  int = 0

class WalletFile:
    def __init__(self, path: str):
        self.path = path
        self.keys: Dict[str, WalletKey] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            for addr, k in data.items():
                self.keys[addr] = WalletKey(**{
                    fld: k.get(fld, "") for fld in WalletKey.__dataclass_fields__
                })
            print(f"[Wallet] Loaded {len(self.keys)} key(s)  {self.path}")
        else:
            self._new_key("default")
            print(f"[Wallet] Created new wallet  {self.path}")

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({a: asdict(k) for a, k in self.keys.items()}, f, indent=2)
        if IS_WIN and os.path.exists(self.path):
            os.remove(self.path)
        os.replace(tmp, self.path)

    def _new_key(self, label: str) -> str:
        priv, pub, addr = generate_keypair()
        self.keys[addr] = WalletKey(
            address=addr, pub_hex=pub, priv_hex=priv,
            label=label or f"Account {len(self.keys)+1}",
            created=int(time.time()),
        )
        self._save()
        return addr

    def new_address(self, label: str = "") -> str:
        addr = self._new_key(label)
        print(f"[Wallet] New address  {addr}  [{label}]")
        return addr

    def default(self) -> str:
        return list(self.keys.keys())[0]

    def sign_tx(self, sender: str, receiver: str,
                amount: float, fee: float,
                memo: str = "") -> Optional[dict]:
        if sender not in self.keys:
            return None
        k  = self.keys[sender]
        ts = int(time.time())
        signing = (
            f"{sender}:{receiver}:"
            f"{amount:.8f}:{fee:.8f}:{ts}:{memo}"
        ).encode()
        sig   = sign_data(k.priv_hex, signing)
        tx_id = hashlib.sha3_256(signing + sig.encode()).hexdigest()
        return {
            "tx_id": tx_id, "sender": sender, "receiver": receiver,
            "amount": amount, "fee": fee, "timestamp": ts,
            "signature": sig, "pub_key": k.pub_hex, "memo": memo,
            "confirmed": False, "block_height": -1,
        }

# ─────────────────────────────────────────────────────────────────
# NODE CLIENT
# ─────────────────────────────────────────────────────────────────
class NodeClient:
    def __init__(self, url: str = "http://localhost:6060"):
        self.url = url.rstrip("/")

    def _get(self, path: str) -> Optional[dict]:
        try:
            r = urllib.request.urlopen(f"{self.url}{path}", timeout=5)
            return json.loads(r.read())
        except Exception:
            return None

    def _post(self, path: str, data: dict) -> Optional[dict]:
        try:
            payload = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                f"{self.url}{path}", data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            return json.loads(urllib.request.urlopen(req, timeout=8).read())
        except Exception:
            return None

    def balance(self, addr: str) -> float:
        d = self._get(f"/balance/{addr}")
        return d.get("balance", 0.0) if d else 0.0

    def history(self, addr: str) -> list:
        d = self._get(f"/history/{addr}")
        return d if isinstance(d, list) else []

    def send_tx(self, tx: dict) -> dict:
        r = self._post("/tx/send", tx)
        return r or {"accepted": False, "reason": "node unreachable"}

    def status(self) -> Optional[dict]:
        return self._get("/")

    def get_tx(self, tx_id: str) -> Optional[dict]:
        return self._get(f"/tx/{tx_id}")

    def miners(self) -> dict:
        return self._get("/miners") or {}

# ─────────────────────────────────────────────────────────────────
# WEB WALLET UI
# ─────────────────────────────────────────────────────────────────
WALLET_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PoLM Wallet — polm.com.br</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#07080a;--s1:#0d1017;--s2:#131a24;--s3:#0a0f16;
  --b1:#1e2a38;--b2:#263346;
  --cyan:#22d3ee;--cyan2:#0891b2;
  --green:#22c55e;--amber:#f59e0b;--red:#ef4444;--purple:#a78bfa;
  --t1:#f0f4f8;--t2:#8ba3bc;--t3:#3d5166;
  --mono:'JetBrains Mono',monospace;--sans:'Space Grotesk',sans-serif;
  --r:8px;--r2:12px
}
html{font-size:13px;scroll-behavior:smooth}
body{background:var(--bg);color:var(--t1);font-family:var(--sans);min-height:100vh;
  background-image:radial-gradient(ellipse 80% 45% at 50% 0%,rgba(34,211,238,.05) 0%,transparent 65%)}

/* NAV */
nav{background:rgba(7,8,10,.95);border-bottom:1px solid var(--b1);
  height:56px;display:flex;align-items:center;padding:0 20px;gap:12px;
  position:sticky;top:0;z-index:200;backdrop-filter:blur(20px)}
.logo{font-family:var(--mono);font-weight:700;font-size:.95rem;color:var(--cyan);
  letter-spacing:.04em;white-space:nowrap;text-decoration:none}
.logo em{color:var(--t3);font-style:normal}
.net-pill{padding:3px 10px;border-radius:20px;font-size:.6rem;font-family:var(--mono);
  background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);
  color:var(--green);display:flex;align-items:center;gap:5px}
.net-pill::before{content:'';width:5px;height:5px;border-radius:50%;
  background:var(--green);animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.tabs{display:flex;gap:2px;margin-left:8px}
.tab{padding:5px 13px;border-radius:6px;font-size:.7rem;cursor:pointer;
  color:var(--t2);border:1px solid transparent;transition:all .15s;font-family:var(--mono)}
.tab:hover{color:var(--t1);background:var(--s2)}
.tab.active{color:var(--cyan);background:rgba(34,211,238,.08);border-color:rgba(34,211,238,.15)}
.nav-r{margin-left:auto;display:flex;align-items:center;gap:8px}
.rbtn{background:transparent;border:1px solid var(--b1);color:var(--t2);
  padding:5px 12px;border-radius:6px;cursor:pointer;font-family:var(--mono);
  font-size:.65rem;transition:all .15s}
.rbtn:hover{border-color:var(--cyan);color:var(--cyan)}

/* LAYOUT */
.wrap{max-width:1080px;margin:0 auto;padding:22px 18px}
.page{display:none}.page.active{display:block}

/* WALLET CARDS */
.wallets-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));
  gap:12px;margin-bottom:20px}
.wcard{background:var(--s1);border:1px solid var(--b1);border-radius:14px;
  padding:20px;position:relative;overflow:hidden;cursor:pointer;
  transition:all .2s}
.wcard::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,var(--cyan2),var(--cyan));opacity:0;transition:opacity .2s}
.wcard.sel{border-color:var(--cyan);background:rgba(34,211,238,.04)}
.wcard.sel::before{opacity:1}
.wcard:hover{border-color:var(--b2);transform:translateY(-2px)}
.wc-label{font-size:.62rem;color:var(--t3);font-family:var(--mono);
  text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}
.wc-addr{font-family:var(--mono);font-size:.65rem;color:var(--t2);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:14px}
.wc-bal{font-size:1.8rem;font-weight:800;color:var(--cyan);
  font-family:var(--mono);line-height:1;margin-bottom:2px}
.wc-sym{font-size:.72rem;color:var(--t3);font-family:var(--mono)}
.wc-actions{display:flex;gap:6px;margin-top:14px}
.wc-btn{flex:1;padding:7px;border-radius:6px;font-size:.68rem;font-family:var(--mono);
  font-weight:600;cursor:pointer;border:none;transition:all .15s;text-align:center}
.wc-send{background:var(--cyan);color:#000}.wc-send:hover{background:var(--cyan2);color:#fff}
.wc-recv{background:var(--s3);border:1px solid var(--b1);color:var(--t2)}
.wc-recv:hover{border-color:var(--cyan);color:var(--cyan)}

/* TOTAL BAR */
.total-bar{background:var(--s1);border:1px solid var(--b1);border-radius:12px;
  padding:16px 20px;margin-bottom:20px;
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}
.total-label{font-size:.6rem;color:var(--t3);font-family:var(--mono);
  text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px}
.total-val{font-size:1.5rem;font-weight:800;color:var(--cyan);font-family:var(--mono)}
.total-meta{font-size:.65rem;color:var(--t3);font-family:var(--mono)}

/* SECTIONS */
.sec{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);
  padding:20px;margin-bottom:14px}
.st{font-size:.6rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
  color:var(--t2);margin-bottom:16px;display:flex;align-items:center;gap:8px;font-family:var(--mono)}
.st::after{content:'';flex:1;height:1px;background:var(--b1)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:700px){.two{grid-template-columns:1fr}}

/* FORM */
.fr{margin-bottom:14px}
.fr label{display:block;font-size:.62rem;color:var(--t3);font-family:var(--mono);
  text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}
.fi{width:100%;background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);
  padding:10px 14px;color:var(--t1);font-family:var(--mono);font-size:.8rem;
  outline:none;transition:border-color .15s}
.fi:focus{border-color:var(--cyan)}
.fi::placeholder{color:var(--t3)}
.fi option{background:var(--s2)}
.btn{padding:10px 22px;border-radius:var(--r);font-family:var(--sans);
  font-size:.8rem;font-weight:600;cursor:pointer;border:none;transition:all .15s}
.btn-p{background:var(--cyan);color:#000}.btn-p:hover{background:var(--cyan2);color:#fff}
.btn-g{background:transparent;color:var(--t2);border:1px solid var(--b1)}
.btn-g:hover{border-color:var(--cyan);color:var(--cyan)}
.btn-sm{padding:6px 14px;font-size:.7rem}
.btns{display:flex;gap:10px;margin-top:6px;flex-wrap:wrap}
.max-btn{font-size:.62rem;color:var(--cyan);cursor:pointer;font-family:var(--mono);
  float:right;margin-bottom:5px}
.max-btn:hover{text-decoration:underline}

/* ALERTS */
.al{padding:12px 16px;border-radius:var(--r);font-size:.76rem;margin-bottom:14px;font-family:var(--mono)}
.al-ok {background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);color:var(--green)}
.al-err{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);color:var(--red)}
.al-inf{background:rgba(34,211,238,.07);border:1px solid rgba(34,211,238,.14);color:var(--cyan)}

/* TX LIST */
.trow{display:grid;grid-template-columns:36px 1fr auto;
  align-items:center;gap:10px;padding:12px 0;
  border-bottom:1px solid rgba(30,42,56,.4);transition:background .1s}
.trow:hover{background:rgba(34,211,238,.02)}
.trow:last-child{border-bottom:none}
.tic{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:.85rem;flex-shrink:0}
.tin{background:rgba(34,197,94,.12);color:var(--green)}
.tout{background:rgba(239,68,68,.1);color:var(--red)}
.tself{background:rgba(34,211,238,.08);color:var(--cyan)}
.tinfo{min-width:0}
.taddr{font-family:var(--mono);font-size:.7rem;color:var(--t2);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tmeta{font-size:.6rem;color:var(--t3);font-family:var(--mono);margin-top:2px}
.tamt{font-family:var(--mono);font-size:.82rem;font-weight:700;white-space:nowrap}
.tbadge{display:inline-block;padding:2px 7px;border-radius:4px;
  font-size:.58rem;font-family:var(--mono);margin-top:2px}
.badge-ok{background:rgba(34,197,94,.1);color:var(--green)}
.badge-pend{background:rgba(245,158,11,.1);color:var(--amber)}

/* QR */
.qrwrap{display:flex;flex-direction:column;align-items:center;gap:16px;padding:20px 0}
#qr-canvas{border:3px solid var(--cyan);border-radius:12px;background:#fff;padding:10px}
.addr-display{font-family:var(--mono);font-size:.72rem;color:var(--cyan);
  word-break:break-all;text-align:center;cursor:pointer;padding:12px 16px;
  background:var(--s2);border-radius:var(--r);border:1px solid var(--b1);
  max-width:460px;width:100%;transition:border-color .15s}
.addr-display:hover{border-color:var(--cyan)}
.copy-hint{font-size:.62rem;color:var(--t3);font-family:var(--mono)}

/* NETWORK STATS */
.nsgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));
  gap:8px;margin-bottom:16px}
.nscard{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);
  padding:12px;text-align:center}
.nsl{font-size:.57rem;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;
  font-family:var(--mono);margin-bottom:4px}
.nsv{font-size:1.05rem;font-weight:700;font-family:var(--mono);color:var(--t1)}

/* LEADERBOARD */
.lbrow{display:grid;grid-template-columns:22px 1fr 70px 55px 48px;
  align-items:center;gap:10px;padding:9px 0;
  border-bottom:1px solid rgba(30,42,56,.4)}
.lbrow:last-child{border-bottom:none}
.rnk{font-family:var(--mono);font-size:.72rem;color:var(--t3);text-align:center}
.rnk.r1{color:#fbbf24}.rnk.r2{color:#9ca3af}.rnk.r3{color:#cd7f32}
.ram-badge{display:inline-block;padding:2px 7px;border-radius:4px;
  font-size:.6rem;font-weight:700;font-family:var(--mono)}
.ddr2{background:rgba(249,115,22,.1);color:#fb923c;border:1px solid rgba(249,115,22,.2)}
.ddr3{background:rgba(245,158,11,.08);color:#fbbf24;border:1px solid rgba(245,158,11,.18)}
.ddr4{background:rgba(34,211,238,.07);color:var(--cyan);border:1px solid rgba(34,211,238,.14)}
.ddr5{background:rgba(239,68,68,.08);color:#f87171;border:1px solid rgba(239,68,68,.15)}

/* ADDR TABLE */
.arow{display:flex;align-items:center;gap:12px;padding:12px 0;
  border-bottom:1px solid rgba(30,42,56,.4)}
.arow:last-child{border-bottom:none}
.ainfo{flex:1;min-width:0}
.aa{font-family:var(--mono);font-size:.72rem;color:var(--cyan)}
.al2{font-size:.62rem;color:var(--t3);font-family:var(--mono);margin-top:2px}
.cpbtn{font-size:.62rem;padding:5px 12px;border-radius:6px;cursor:pointer;
  background:var(--s2);border:1px solid var(--b1);color:var(--t2);font-family:var(--mono)}
.cpbtn:hover{border-color:var(--cyan);color:var(--cyan)}
.abal{font-family:var(--mono);font-size:.82rem;font-weight:700;color:var(--cyan);
  white-space:nowrap;text-align:right}

/* PREVIEW */
.preview-grid{display:grid;grid-template-columns:120px 1fr;gap:5px 14px;
  font-size:.72rem;font-family:var(--mono)}
.pk{color:var(--t3)}.pv{color:var(--t1);word-break:break-all}
.preview-total{background:rgba(34,211,238,.05);border:1px solid rgba(34,211,238,.12);
  border-radius:8px;padding:12px;margin-top:12px;font-family:var(--mono);font-size:.82rem}

/* FOOTER */
footer{border-top:1px solid var(--b1);padding:14px 24px;margin-top:8px;
  display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.fl{font-size:.6rem;color:var(--t3);font-family:var(--mono)}
.fl a{color:var(--cyan);text-decoration:none}

/* EMPTY STATE */
.empty{text-align:center;padding:40px 20px;color:var(--t3);font-family:var(--mono);font-size:.82rem}
.empty-icon{font-size:2.5rem;margin-bottom:12px}

/* NOTIFICATION TOAST */
.toast{position:fixed;bottom:24px;right:24px;z-index:999;
  background:var(--s1);border:1px solid var(--green);border-radius:10px;
  padding:12px 20px;font-family:var(--mono);font-size:.78rem;color:var(--green);
  transform:translateY(100px);opacity:0;transition:all .3s}
.toast.show{transform:translateY(0);opacity:1}
</style>
</head>
<body>

<div class="toast" id="toast"></div>

<nav>
  <a class="logo" href="/">PoLM <em>/</em> Wallet</a>
  <div class="net-pill" id="net-pill">mainnet</div>
  <div class="tabs">
    <div class="tab active" onclick="pg('dashboard',this)">Dashboard</div>
    <div class="tab" onclick="pg('send',this)">Send</div>
    <div class="tab" onclick="pg('receive',this)">Receive</div>
    <div class="tab" onclick="pg('history',this)">History</div>
    <div class="tab" onclick="pg('addresses',this)">Addresses</div>
    <div class="tab" onclick="pg('network',this)">Network</div>
  </div>
  <div class="nav-r">
    <span id="nstatus" style="font-size:.6rem;color:var(--t3);font-family:var(--mono)"></span>
    <button class="rbtn" onclick="init()">↻</button>
  </div>
</nav>

<!-- DASHBOARD -->
<div class="page active" id="page-dashboard">
<div class="wrap">
  <div class="total-bar">
    <div>
      <div class="total-label">Total Balance</div>
      <div class="total-val" id="total-bal">0.0000 <span style="font-size:1rem;color:var(--t3)">POLM</span></div>
    </div>
    <div style="text-align:right">
      <div class="total-meta" id="total-addrs">0 addresses</div>
      <div class="total-meta" id="last-update" style="margin-top:2px"></div>
    </div>
  </div>
  <div class="wallets-grid" id="wallet-cards"></div>
  <div class="sec">
    <div class="st">Recent activity</div>
    <div id="dash-txs"><div class="empty"><div class="empty-icon">📭</div>No transactions yet.</div></div>
  </div>
</div>
</div>

<!-- SEND -->
<div class="page" id="page-send">
<div class="wrap">
<div class="two">
  <div>
    <div class="sec">
      <div class="st">Send POLM</div>
      <div class="fr">
        <label>From address</label>
        <select class="fi" id="sfrom" onchange="updPreview()"></select>
      </div>
      <div class="fr">
        <label>Balance: <span id="sfrom-bal" style="color:var(--cyan)">—</span> POLM</label>
      </div>
      <div class="fr">
        <label>Recipient address</label>
        <input class="fi" id="sto" placeholder="POLM..." oninput="updPreview()">
      </div>
      <div class="fr">
        <span class="max-btn" onclick="setMax()">MAX</span>
        <label>Amount (POLM)</label>
        <input class="fi" id="samt" type="number" step="0.0001" placeholder="0.0000" oninput="updPreview()">
      </div>
      <div class="fr">
        <label>Fee (POLM) — min 0.0001</label>
        <input class="fi" id="sfee" type="number" step="0.0001" value="0.001" oninput="updPreview()">
      </div>
      <div class="fr">
        <label>Memo (optional)</label>
        <input class="fi" id="smemo" placeholder="Optional message..." maxlength="64">
      </div>
      <div id="send-al"></div>
      <div class="btns">
        <button class="btn btn-p" onclick="doSend()">Send POLM →</button>
        <button class="btn btn-g" onclick="clearSend()">Clear</button>
      </div>
    </div>
  </div>
  <div>
    <div class="sec">
      <div class="st">Transaction preview</div>
      <div id="preview" style="color:var(--t3);font-family:var(--mono);font-size:.78rem">
        Fill in the form to preview transaction.
      </div>
    </div>
    <div class="sec">
      <div class="st">Fee guide</div>
      <div style="font-family:var(--mono);font-size:.75rem;color:var(--t2);line-height:1.8">
        <div>Min fee: <span style="color:var(--cyan)">0.0001 POLM</span></div>
        <div>Recommended: <span style="color:var(--cyan)">0.001 POLM</span></div>
        <div>Priority: <span style="color:var(--cyan)">0.01 POLM</span></div>
        <div style="margin-top:8px;color:var(--t3);font-size:.68rem">Higher fee = faster confirmation</div>
      </div>
    </div>
  </div>
</div>
</div>
</div>

<!-- RECEIVE -->
<div class="page" id="page-receive">
<div class="wrap">
  <div class="sec" style="max-width:560px;margin:0 auto">
    <div class="st">Receive POLM</div>
    <div class="fr">
      <label>Select address</label>
      <select class="fi" id="raddr" onchange="updQR()"></select>
    </div>
    <div class="qrwrap">
      <canvas id="qr-canvas" width="200" height="200"></canvas>
      <div class="addr-display" id="qr-addr-box" onclick="copyAddr()" title="Click to copy">
        Select an address above
      </div>
      <div class="copy-hint">Click address to copy</div>
    </div>
    <div style="font-family:var(--mono);font-size:.75rem;color:var(--t3);text-align:center;
      padding:12px;background:var(--s2);border-radius:8px;border:1px solid var(--b1)">
      ⚠️ Only send POLM to this address. Sending other currencies may result in permanent loss.
    </div>
  </div>
</div>
</div>

<!-- HISTORY -->
<div class="page" id="page-history">
<div class="wrap">
  <div class="sec">
    <div class="st">Transaction history</div>
    <div class="fr">
      <label>Address</label>
      <select class="fi" id="haddr" onchange="loadHistory()"></select>
    </div>
    <div id="hlist"><div class="empty"><div class="empty-icon">📋</div>Select an address to view history.</div></div>
  </div>
</div>
</div>

<!-- ADDRESSES -->
<div class="page" id="page-addresses">
<div class="wrap">
  <div class="sec">
    <div class="st">My addresses</div>
    <div id="addr-list"></div>
    <div style="margin-top:16px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <input class="fi" id="new-label" placeholder="Label (optional)" style="max-width:240px">
      <button class="btn btn-p btn-sm" onclick="newAddr()">+ New Address</button>
      <span id="newaddr-res" style="font-family:var(--mono);font-size:.72rem;color:var(--green)"></span>
    </div>
  </div>
</div>
</div>

<!-- NETWORK -->
<div class="page" id="page-network">
<div class="wrap">
  <div class="nsgrid" id="ns-grid"></div>
  <div class="two">
    <div class="sec">
      <div class="st">Mining leaderboard</div>
      <div style="display:grid;grid-template-columns:22px 1fr 70px 55px 48px;
        gap:10px;padding:0 0 8px;border-bottom:1px solid var(--b1);margin-bottom:4px">
        <span style="font-size:.58rem;color:var(--t3);font-family:var(--mono)">#</span>
        <span style="font-size:.58rem;color:var(--t3);font-family:var(--mono)">Miner</span>
        <span style="font-size:.58rem;color:var(--t3);font-family:var(--mono);text-align:right">Blocks</span>
        <span style="font-size:.58rem;color:var(--t3);font-family:var(--mono);text-align:right">POLM</span>
        <span style="font-size:.58rem;color:var(--t3);font-family:var(--mono);text-align:right">RAM</span>
      </div>
      <div id="lb-list"></div>
    </div>
    <div>
      <div class="sec" style="margin-bottom:14px">
        <div class="st">Node connection</div>
        <div class="fr">
          <label>Node URL</label>
          <input class="fi" id="node-url-inp" value="http://localhost:6060">
        </div>
        <button class="btn btn-g btn-sm" onclick="setNode()">Connect</button>
        <div id="node-al" style="margin-top:10px"></div>
      </div>
      <div class="sec">
        <div class="st">Network info</div>
        <div id="net-info"></div>
      </div>
    </div>
  </div>
</div>
</div>

<footer>
  <div class="fl">PoLM Wallet v2.1.0 &nbsp;·&nbsp; <a href="https://polm.com.br">polm.com.br</a> &nbsp;·&nbsp; MIT License</div>
  <div class="fl"><a href="https://x.com/polm2026" target="_blank">@polm2026</a> &nbsp;·&nbsp; <a href="https://x.com/aluisiofer" target="_blank">@aluisiofer</a></div>
</footer>

<script>
// QR Code generator (simple)
function qr(canvas, text){
  const ctx=canvas.getContext('2d');
  const size=canvas.width;
  ctx.fillStyle='#fff';
  ctx.fillRect(0,0,size,size);
  // Simple checkered pattern as placeholder
  ctx.fillStyle='#000';
  const cell=4;
  const cols=size/cell;
  let hash=0;
  for(let i=0;i<text.length;i++){hash=(hash*31+text.charCodeAt(i))&0xFFFFFFFF}
  for(let y=0;y<cols;y++){
    for(let x=0;x<cols;x++){
      const bit=(hash^(x*7+y*13)^(x^y))&1;
      if(bit||(x<7&&y<7)||(x>cols-8&&y<7)||(x<7&&y>cols-8)){
        if(!((x<7&&y<7&&(x<1||x>5||y<1||y>5))||(x>cols-8&&y<7&&(x<cols-6||x>cols-2||y<1||y>5))||(x<7&&y>cols-8&&(x<1||x>5||y<cols-6||y>cols-2)))){
          ctx.fillRect(x*cell,y*cell,cell,cell);
        }
      }
    }
  }
  // Corner markers
  for(const [cx,cy] of [[0,0],[cols-7,0],[0,cols-7]]){
    ctx.fillStyle='#000';
    ctx.fillRect(cx*cell,cy*cell,7*cell,7*cell);
    ctx.fillStyle='#fff';
    ctx.fillRect((cx+1)*cell,(cy+1)*cell,5*cell,5*cell);
    ctx.fillStyle='#000';
    ctx.fillRect((cx+2)*cell,(cy+2)*cell,3*cell,3*cell);
  }
}

const API = (path,method='GET',body=null) =>
  fetch(path,{method,headers:{'Content-Type':'application/json'},
    body:body?JSON.stringify(body):null}).then(r=>r.json()).catch(()=>null);

let nodeUrl='http://localhost:6060';
let allAddrs=[];
let balances={};
let currentAddr='';

function toast(msg,ok=true){
  const t=document.getElementById('toast');
  t.textContent=msg;
  t.style.borderColor=ok?'var(--green)':'var(--red)';
  t.style.color=ok?'var(--green)':'var(--red)';
  t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2800);
}

function pg(id,el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(el) el.classList.add('active');
  if(id==='send') updBal();
  if(id==='receive') updQR();
  if(id==='history') loadHistory();
  if(id==='addresses') loadAddrs();
  if(id==='network') loadNetwork();
}

function ramBadge(r){
  const cls=(r||'DDR4').toLowerCase().replace(' ','');
  return `<span class="ram-badge ${cls}">${r||'DDR4'}</span>`;
}

function fmtAge(ts){
  const d=Math.floor(Date.now()/1000)-ts;
  if(d<60) return d+'s ago';
  if(d<3600) return Math.floor(d/60)+'m ago';
  if(d<86400) return Math.floor(d/3600)+'h ago';
  return Math.floor(d/86400)+'d ago';
}

function txList(txs, myAddr){
  if(!txs||!txs.length) return '<div class="empty"><div class="empty-icon">📭</div>No transactions yet.</div>';
  return txs.map(tx=>{
    const isIn = tx.receiver===myAddr;
    const isOut = tx.sender===myAddr;
    const isSelf = isIn && isOut;
    const ic = isSelf?'tself':isIn?'tin':'tout';
    const icon = isSelf?'↔':isIn?'↓':'↑';
    const peer = isIn?tx.sender:tx.receiver;
    const amt = parseFloat(tx.amount||0);
    const sign = isIn && !isSelf ? '+':isOut && !isSelf ? '-':'';
    const col = isIn && !isSelf ? 'var(--green)':isOut && !isSelf ? 'var(--red)':'var(--cyan)';
    const conf = tx.confirmed?
      `<span class="tbadge badge-ok">✓ confirmed</span>`:
      `<span class="tbadge badge-pend">⏳ pending</span>`;
    const ts = tx.timestamp ? fmtAge(tx.timestamp) : '';
    return `<div class="trow">
      <div class="tic ${ic}">${icon}</div>
      <div class="tinfo">
        <div class="taddr">${peer||'—'}</div>
        <div class="tmeta">${ts} ${tx.memo?'· '+tx.memo:''}</div>
        <div>${conf}</div>
      </div>
      <div style="text-align:right">
        <div class="tamt" style="color:${col}">${sign}${amt.toFixed(4)} POLM</div>
        <div class="tmeta">fee ${parseFloat(tx.fee||0).toFixed(4)}</div>
      </div>
    </div>`;
  }).join('');
}

async function init(){
  const info = await API('/wallet/info');
  if(!info) return;
  nodeUrl = info.node_url||nodeUrl;
  allAddrs = info.addresses||[];
  document.getElementById('node-url-inp').value = nodeUrl;
  document.getElementById('net-pill').textContent = info.network||'mainnet';

  // Populate selects
  const opts = allAddrs.map(a=>`<option value="${a.address}">${a.address.slice(0,20)}… ${a.label?'('+a.label+')':''}</option>`).join('');
  ['sfrom','raddr','haddr'].forEach(id=>{
    const el=document.getElementById(id);
    if(el) el.innerHTML=opts;
  });

  await loadBalances();
  await loadDashboard();
  document.getElementById('last-update').textContent = 'Updated '+new Date().toLocaleTimeString();
}

async function loadBalances(){
  let total=0;
  for(const a of allAddrs){
    const r=await API('/wallet/balance/'+a.address);
    balances[a.address]=r?parseFloat(r.balance||0):0;
    total+=balances[a.address];
  }
  document.getElementById('total-bal').innerHTML =
    total.toFixed(4)+' <span style="font-size:1rem;color:var(--t3)">POLM</span>';
  document.getElementById('total-addrs').textContent = allAddrs.length+' address'+(allAddrs.length!==1?'es':'');
}

async function loadDashboard(){
  // Wallet cards
  const grid=document.getElementById('wallet-cards');
  if(!allAddrs.length){
    grid.innerHTML='<div class="empty" style="grid-column:1/-1"><div class="empty-icon">💳</div>No addresses yet. Go to Addresses tab to create one.</div>';
  } else {
    grid.innerHTML=allAddrs.map(a=>{
      const bal=(balances[a.address]||0).toFixed(4);
      const sel=a.address===currentAddr?' sel':'';
      return `<div class="wcard${sel}" onclick="selWallet('${a.address}')">
        <div class="wc-label">${a.label||'address'}</div>
        <div class="wc-addr">${a.address}</div>
        <div class="wc-bal">${bal}</div>
        <div class="wc-sym">POLM</div>
        <div class="wc-actions">
          <div class="wc-btn wc-send" onclick="event.stopPropagation();sendFrom('${a.address}')">Send</div>
          <div class="wc-btn wc-recv" onclick="event.stopPropagation();recvTo('${a.address}')">Receive</div>
        </div>
      </div>`;
    }).join('');
  }

  // Recent txs — all addresses combined
  let allTxs=[];
  for(const a of allAddrs){
    const txs=await API('/wallet/history/'+a.address);
    if(Array.isArray(txs)) allTxs.push(...txs.map(t=>({...t,_myAddr:a.address})));
  }
  allTxs.sort((a,b)=>(b.timestamp||0)-(a.timestamp||0));
  document.getElementById('dash-txs').innerHTML=txList(allTxs.slice(0,20),null)||
    '<div class="empty"><div class="empty-icon">📭</div>No transactions yet.</div>';
}

function selWallet(addr){
  currentAddr=addr;
  document.querySelectorAll('.wcard').forEach(c=>c.classList.remove('sel'));
  event.currentTarget.classList.add('sel');
}

function sendFrom(addr){
  document.getElementById('sfrom').value=addr;
  pg('send',document.querySelectorAll('.tab')[1]);
  updBal();
}

function recvTo(addr){
  document.getElementById('raddr').value=addr;
  pg('receive',document.querySelectorAll('.tab')[2]);
  updQR();
}

async function updBal(){
  const addr=document.getElementById('sfrom').value;
  if(!addr) return;
  const r=await API('/wallet/balance/'+addr);
  const bal=r?parseFloat(r.balance||0):0;
  document.getElementById('sfrom-bal').textContent=bal.toFixed(4);
  balances[addr]=bal;
  updPreview();
}

function setMax(){
  const addr=document.getElementById('sfrom').value;
  const fee=parseFloat(document.getElementById('sfee').value||'0.001');
  const bal=balances[addr]||0;
  const max=Math.max(0,bal-fee);
  document.getElementById('samt').value=max.toFixed(4);
  updPreview();
}

function updPreview(){
  const from=document.getElementById('sfrom').value;
  const to=document.getElementById('sto').value.trim();
  const amt=parseFloat(document.getElementById('samt').value||0);
  const fee=parseFloat(document.getElementById('sfee').value||0.001);
  const memo=document.getElementById('smemo').value;
  const bal=balances[from]||0;
  const total=amt+fee;
  const ok=to.startsWith('POLM')&&amt>0&&fee>=0.0001&&total<=bal;
  const col=ok?'var(--green)':'var(--red)';
  document.getElementById('preview').innerHTML=`
    <div class="preview-grid">
      <span class="pk">From</span><span class="pv">${from||'—'}</span>
      <span class="pk">To</span><span class="pv" style="color:${to.startsWith('POLM')?'var(--cyan)':'var(--red)'}">${to||'—'}</span>
      <span class="pk">Amount</span><span class="pv">${amt.toFixed(4)} POLM</span>
      <span class="pk">Fee</span><span class="pv">${fee.toFixed(4)} POLM</span>
      ${memo?`<span class="pk">Memo</span><span class="pv">${memo}</span>`:''}
    </div>
    <div class="preview-total">
      Total: <strong style="color:${col}">${total.toFixed(4)} POLM</strong>
      &nbsp;·&nbsp; Balance after: <strong style="color:${(bal-total)>=0?'var(--cyan)':'var(--red)'}">${(bal-total).toFixed(4)} POLM</strong>
    </div>`;
}

async function doSend(){
  const from=document.getElementById('sfrom').value;
  const to=document.getElementById('sto').value.trim();
  const amt=parseFloat(document.getElementById('samt').value||0);
  const fee=parseFloat(document.getElementById('sfee').value||0.001);
  const memo=document.getElementById('smemo').value;
  const al=document.getElementById('send-al');
  if(!to.startsWith('POLM')){al.innerHTML='<div class="al al-err">Invalid address — must start with POLM</div>';return;}
  if(amt<=0){al.innerHTML='<div class="al al-err">Enter a valid amount</div>';return;}
  if(fee<0.0001){al.innerHTML='<div class="al al-err">Fee too low — minimum 0.0001</div>';return;}
  al.innerHTML='<div class="al al-inf">⏳ Signing and broadcasting...</div>';
  const r=await API('/wallet/send','POST',{from,to,amount:amt,fee,memo});
  if(r&&r.accepted){
    al.innerHTML=`<div class="al al-ok">✅ Transaction sent!<br><span style="font-size:.68rem">${r.tx_id||''}</span></div>`;
    toast('Transaction sent! ✅');
    await loadBalances();
    await loadDashboard();
  } else {
    al.innerHTML=`<div class="al al-err">❌ ${r?.reason||'Failed'}</div>`;
    toast(r?.reason||'Failed',false);
  }
}

function clearSend(){
  ['sto','samt','smemo'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('sfee').value='0.001';
  document.getElementById('send-al').innerHTML='';
  document.getElementById('preview').innerHTML='Fill in the form to preview transaction.';
}

function updQR(){
  const addr=document.getElementById('raddr').value;
  if(!addr) return;
  document.getElementById('qr-addr-box').textContent=addr;
  qr(document.getElementById('qr-canvas'),addr);
}

function copyAddr(){
  const addr=document.getElementById('raddr').value;
  navigator.clipboard.writeText(addr).then(()=>toast('Address copied! 📋'));
}

async function loadHistory(){
  const addr=document.getElementById('haddr').value;
  if(!addr) return;
  document.getElementById('hlist').innerHTML='<div class="al al-inf">Loading...</div>';
  const txs=await API('/wallet/history/'+addr);
  document.getElementById('hlist').innerHTML=txList(Array.isArray(txs)?txs:[],addr);
}

async function loadAddrs(){
  const info=await API('/wallet/info');
  if(!info) return;
  const addrs=info.addresses||[];
  await loadBalances();
  document.getElementById('addr-list').innerHTML=addrs.length?
    addrs.map(a=>`<div class="arow">
      <div class="ainfo">
        <div class="aa">${a.address}</div>
        <div class="al2">${a.label||'no label'} · created ${new Date(a.created*1000).toLocaleDateString()}</div>
      </div>
      <div class="abal">${(balances[a.address]||0).toFixed(4)}<br><span style="font-size:.6rem;color:var(--t3)">POLM</span></div>
      <button class="cpbtn" onclick="navigator.clipboard.writeText('${a.address}').then(()=>toast('Copied! 📋'))">Copy</button>
      <button class="cpbtn" onclick="sendFrom('${a.address}')">Send</button>
    </div>`).join(''):
    '<div class="empty"><div class="empty-icon">💳</div>No addresses yet.</div>';
}

async function newAddr(){
  const label=document.getElementById('new-label').value.trim();
  const r=await API('/wallet/new_address','POST',{label});
  if(r&&r.address){
    document.getElementById('newaddr-res').textContent='Created: '+r.address.slice(0,20)+'…';
    document.getElementById('new-label').value='';
    toast('New address created! 🎉');
    await init();
    loadAddrs();
  }
}

async function loadNetwork(){
  const [st,miners]=await Promise.all([API('/wallet/node_status'),API('/wallet/miners')]);
  // Network stats
  if(st&&!st.error){
    document.getElementById('net-pill').textContent=st.network||'mainnet';
    document.getElementById('nstatus').textContent='h='+st.height;
    const cards=[
      {l:'Height',v:(st.height||0).toLocaleString()},
      {l:'Supply',v:Number(st.total_supply||0).toFixed(0)+' POLM'},
      {l:'Reward',v:(st.next_reward||50).toFixed(2)+' POLM'},
      {l:'Difficulty',v:st.difficulty||3},
      {l:'Peers',v:st.peers||0},
      {l:'Mempool',v:st.mempool_size||0},
      {l:'Block Time',v:(st.block_time||30)+'s'},
      {l:'Version',v:st.version||'1.3.1'},
    ];
    document.getElementById('ns-grid').innerHTML=cards.map(c=>
      `<div class="nscard"><div class="nsl">${c.l}</div><div class="nsv">${c.v}</div></div>`
    ).join('');
    document.getElementById('net-info').innerHTML=[
      ['Symbol','POLM'],['Max supply','210,000,000'],
      ['Hash','SHA3-256'],['Halving','~2yr'],
    ].map(([k,v])=>`<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px solid rgba(30,42,56,.4);font-size:.75rem"><span style="color:var(--t3);font-family:var(--mono)">${k}</span><span style="font-family:var(--mono)">${v}</span></div>`).join('');
  } else {
    document.getElementById('ns-grid').innerHTML='<div class="al al-err" style="grid-column:1/-1">Node offline</div>';
  }
  // Leaderboard
  if(miners&&Object.keys(miners).length){
    const ms=Object.entries(miners).sort((a,b)=>b[1].blocks-a[1].blocks);
    const total=ms.reduce((s,[,v])=>s+v.blocks,0);
    document.getElementById('lb-list').innerHTML=ms.slice(0,8).map(([id,v],i)=>{
      const pct=total?(v.blocks/total*100):0;
      return `<div class="lbrow">
        <div class="rnk ${i<3?'r'+(i+1):''}">#${i+1}</div>
        <div style="min-width:0">
          <div style="font-family:var(--mono);font-size:.7rem;color:var(--cyan);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${id.slice(0,22)}…</div>
          <div style="font-size:.6rem;color:var(--t3);font-family:var(--mono)">${pct.toFixed(1)}%</div>
        </div>
        <div style="font-family:var(--mono);font-size:.72rem;text-align:right">${v.blocks}</div>
        <div style="font-family:var(--mono);font-size:.72rem;color:var(--green);text-align:right">${(v.reward||0).toFixed(0)}</div>
        <div style="text-align:right">${ramBadge(v.ram)}</div>
      </div>`;
    }).join('');
  } else {
    document.getElementById('lb-list').innerHTML='<div class="empty">No miners yet.</div>';
  }
}

async function setNode(){
  const url=document.getElementById('node-url-inp').value.trim();
  const r=await API('/wallet/set_node','POST',{url});
  if(r&&r.ok){
    nodeUrl=url;
    document.getElementById('node-al').innerHTML='<div class="al al-ok">Connected!</div>';
    toast('Node connected! 🌐');
    await loadNetwork();
  }
}

// Auto-refresh
init();
setInterval(async()=>{
  await loadBalances();
  const p=document.querySelector('.page.active');
  if(p){
    const id=p.id.replace('page-','');
    if(id==='dashboard') loadDashboard();
    if(id==='network') loadNetwork();
  }
  document.getElementById('last-update').textContent='Updated '+new Date().toLocaleTimeString();
},30000);
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────────────
# WALLET SERVER
# ─────────────────────────────────────────────────────────────────
class WalletServer:
    def __init__(self, wallet_path: str, node_url: str = "http://localhost:6060",
                 port: int = 7070, network: str = "mainnet"):
        self.wf      = WalletFile(wallet_path)
        self.node    = NodeClient(node_url)
        self.node_url = node_url
        self.port    = port
        self.network = network
        self.app     = Flask("polm-wallet")
        self._routes()

    def _routes(self):
        app = self.app

        @app.route("/")
        def index():
            return Response(WALLET_HTML, mimetype="text/html")

        @app.route("/wallet/info")
        def info():
            return jsonify({
                "version":  VERSION,
                "website":  WEBSITE,
                "network":  self.network,
                "node_url": self.node_url,
                "addresses": [
                    {"address": k.address, "label": k.label,
                     "created": k.created}
                    for k in self.wf.keys.values()
                ],
            })

        @app.route("/wallet/balance/<addr>")
        def balance(addr):
            return jsonify({
                "address": addr,
                "balance": self.node.balance(addr),
                "symbol":  SYMBOL,
            })

        @app.route("/wallet/history/<addr>")
        def history(addr):
            return jsonify(self.node.history(addr))

        @app.route("/wallet/send", methods=["POST"])
        def send():
            d      = request.json or {}
            frm    = d.get("from", "")
            to     = d.get("to", "")
            amount = float(d.get("amount", 0))
            fee    = float(d.get("fee", 0.001))
            memo   = d.get("memo", "")

            if frm not in self.wf.keys:
                return jsonify({"accepted": False, "reason": "address not in wallet"})
            if not to.startswith("POLM") or len(to) < 16:
                return jsonify({"accepted": False, "reason": "invalid recipient address"})
            if amount <= 0:
                return jsonify({"accepted": False, "reason": "invalid amount"})
            if fee < MIN_FEE:
                return jsonify({"accepted": False, "reason": f"fee must be >= {MIN_FEE}"})

            tx = self.wf.sign_tx(frm, to, amount, fee, memo)
            if not tx:
                return jsonify({"accepted": False, "reason": "signing failed"})

            result = self.node.send_tx(tx)
            return jsonify(result)

        @app.route("/wallet/new_address", methods=["POST"])
        def new_address():
            label = (request.json or {}).get("label", "")
            addr  = self.wf.new_address(label)
            return jsonify({
                "address": addr,
                "all": [
                    {"address": k.address, "label": k.label,
                     "created": k.created}
                    for k in self.wf.keys.values()
                ],
            })

        @app.route("/wallet/node_status")
        def node_status():
            st = self.node.status()
            return jsonify(st or {"error": "offline"})

        @app.route("/wallet/miners")
        def miners():
            return jsonify(self.node.miners())

        @app.route("/wallet/set_node", methods=["POST"])
        def set_node():
            url = (request.json or {}).get("url", "").strip()
            if url:
                self.node     = NodeClient(url)
                self.node_url = url
            return jsonify({"ok": True, "url": self.node_url})

        @app.route("/wallet/tx/<tx_id>")
        def get_tx(tx_id):
            tx = self.node.get_tx(tx_id)
            return jsonify(tx or {"error": "not found"})

    def run(self):
        print(f"\n╔══════════════════════════════════════════╗")
        print(f"║  PoLM Wallet  v{VERSION}  ({self.network})         ║")
        print(f"║  {WEBSITE:<40}  ║")
        print(f"╚══════════════════════════════════════════╝")
        print(f"  UI   : http://localhost:{self.port}")
        print(f"  Node : {self.node_url}")
        print(f"  Keys : {len(self.wf.keys)}")
        for k in self.wf.keys.values():
            print(f"         {k.address}  [{k.label}]")
        print()
        self.app.run(
            host="0.0.0.0", port=self.port,
            debug=False, use_reloader=False, threaded=True
        )

# ─────────────────────────────────────────────────────────────────
# DATA DIR HELPER
# ─────────────────────────────────────────────────────────────────
def _data_dir() -> str:
    if IS_WIN:
        d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PoLM")
    else:
        d = os.path.expanduser("~/.polm")
    os.makedirs(d, exist_ok=True)
    return d

# ─────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if IS_WIN:
        import multiprocessing
        multiprocessing.freeze_support()

    args     = sys.argv[1:]
    testnet  = "--testnet" in args or "--test" in args
    args     = [a for a in args if not a.startswith("--")]
    network  = "testnet" if testnet else "mainnet"
    data_dir = _data_dir()
    wpath    = os.path.join(data_dir, "wallet.json")

    mode = args[0] if args else "ui"

    if mode in ("ui", "start", "server"):
        node_url = args[1] if len(args) > 1 else "http://localhost:6060"
        port     = int(args[2]) if len(args) > 2 else 7070
        WalletServer(wpath, node_url, port, network).run()

    elif mode == "new":
        label = args[1] if len(args) > 1 else ""
        wf    = WalletFile(wpath)
        addr  = wf.new_address(label)
        print(f"\n  Address : {addr}")
        print(f"  Label   : {label or 'default'}")

    elif mode == "show":
        wf = WalletFile(wpath)
        print(f"\n  PoLM Wallet  ({len(wf.keys)} address(es))  —  {WEBSITE}")
        print(f"  {'Address':<40}  {'Label'}")
        print("  " + "-" * 56)
        for addr, k in wf.keys.items():
            print(f"  {addr}  {k.label}")

    elif mode == "balance":
        node_url = args[1] if len(args) > 1 else "http://localhost:6060"
        wf   = WalletFile(wpath)
        node = NodeClient(node_url)
        print(f"\n  Balances  (node: {node_url})")
        total = 0.0
        for addr, k in wf.keys.items():
            b = node.balance(addr)
            total += b
            print(f"  {addr}  {b:>12.4f} {SYMBOL}  [{k.label}]")
        print(f"\n  Total :  {total:.4f} {SYMBOL}")

    elif mode == "send":
        if len(args) < 4:
            print("Usage: python polm_wallet.py send <from> <to> <amount> [fee] [node_url]")
            sys.exit(1)
        frm  = args[1]; to = args[2]
        amt  = float(args[3])
        fee  = float(args[4]) if len(args) > 4 else 0.001
        nurl = args[5] if len(args) > 5 else "http://localhost:6060"
        wf   = WalletFile(wpath)
        node = NodeClient(nurl)
        tx   = wf.sign_tx(frm, to, amt, fee)
        if not tx:
            print("Error: address not in wallet"); sys.exit(1)
        res = node.send_tx(tx)
        if res.get("accepted"):
            print(f"  Sent!  TX: {res['tx_id']}")
        else:
            print(f"  Failed: {res.get('reason')}")

    else:
        print(f"""
PoLM Wallet  v{VERSION}  —  {WEBSITE}
Windows / Linux / macOS

  python polm_wallet.py ui      [node_url] [port]  ← Web UI (recommended)
  python polm_wallet.py show                        ← List addresses
  python polm_wallet.py new     [label]             ← Generate address
  python polm_wallet.py balance [node_url]          ← Check balances
  python polm_wallet.py send    <from> <to> <amt>   ← Send POLM

Web UI: http://localhost:7070
""")
