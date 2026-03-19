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
  --bg:#07080a;--s1:#0d1017;--s2:#131a24;--s3:#18202c;
  --b1:#1e2a38;--b2:#263346;
  --cyan:#22d3ee;--cyan2:#0891b2;
  --green:#22c55e;--amber:#f59e0b;--red:#ef4444;--purple:#a78bfa;
  --t1:#f0f4f8;--t2:#8ba3bc;--t3:#3d5166;
  --mono:'JetBrains Mono',monospace;
  --sans:'Space Grotesk',sans-serif;
  --r:8px;--r2:12px;
}
html{font-size:13px;scroll-behavior:smooth}
body{background:var(--bg);color:var(--t1);font-family:var(--sans);min-height:100vh;
  background-image:radial-gradient(ellipse 80% 45% at 50% 0%,rgba(34,211,238,.05) 0%,transparent 65%)}

/* ── NAV ── */
nav{background:rgba(13,16,23,.98);border-bottom:1px solid var(--b1);
  height:56px;display:flex;align-items:center;padding:0 24px;gap:14px;
  position:sticky;top:0;z-index:200;backdrop-filter:blur(16px)}
.logo{font-family:var(--mono);font-weight:700;font-size:.95rem;color:var(--cyan);
  letter-spacing:.04em;white-space:nowrap;text-decoration:none}
.logo em{color:var(--t3);font-style:normal;font-weight:300}
.site{font-size:.6rem;color:var(--t3);font-family:var(--mono);
  border-left:1px solid var(--b1);padding-left:12px;white-space:nowrap}
.pill{padding:3px 10px;border-radius:20px;font-size:.6rem;font-family:var(--mono)}
.net-pill{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);
  color:var(--green);display:flex;align-items:center;gap:5px}
.net-pill::before{content:'';width:5px;height:5px;border-radius:50%;
  background:var(--green);animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.tabs{display:flex;gap:2px;margin-left:4px}
.tab{padding:5px 13px;border-radius:6px;font-size:.7rem;cursor:pointer;
  color:var(--t2);border:1px solid transparent;transition:all .15s;font-family:var(--mono)}
.tab:hover{color:var(--t1);background:var(--s2)}
.tab.active{color:var(--cyan);background:rgba(34,211,238,.08);border-color:rgba(34,211,238,.15)}
.nav-r{margin-left:auto;display:flex;align-items:center;gap:8px}
#nstatus{font-size:.6rem;color:var(--t3);font-family:var(--mono)}

.wrap{max-width:1080px;margin:0 auto;padding:22px 18px}
.page{display:none}.page.active{display:block}

/* ── BALANCE CARDS ── */
.bgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px;margin-bottom:20px}
.bcard{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:18px;
  position:relative;overflow:hidden;cursor:pointer;transition:border-color .15s}
.bcard::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--cyan);opacity:.4}
.bcard.sel{border-color:var(--cyan);background:rgba(34,211,238,.04)}
.bcard:hover{border-color:var(--b2)}
.bc-lbl{font-size:.6rem;color:var(--t3);font-family:var(--mono);margin-bottom:4px}
.bc-addr{font-family:var(--mono);font-size:.65rem;color:var(--t2);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-bottom:10px}
.bc-amt{font-size:1.55rem;font-weight:700;color:var(--cyan);font-family:var(--mono);line-height:1}
.bc-sym{font-size:.72rem;color:var(--t3);font-family:var(--mono);margin-left:4px}

/* ── SECTIONS ── */
.sec{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:20px;margin-bottom:14px}
.st{font-size:.6rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
  color:var(--t2);margin-bottom:16px;display:flex;align-items:center;gap:8px;font-family:var(--mono)}
.st::after{content:'';flex:1;height:1px;background:var(--b1)}

/* ── FORM ── */
.fr{margin-bottom:14px}
.fr label{display:block;font-size:.62rem;color:var(--t3);font-family:var(--mono);
  text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px}
.fi{width:100%;background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);
  padding:10px 14px;color:var(--t1);font-family:var(--mono);font-size:.8rem;
  outline:none;transition:border-color .15s}
.fi:focus{border-color:var(--cyan)}
.fi::placeholder{color:var(--t3)}
.fi option{background:var(--s2)}
.fh{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.btn{padding:10px 22px;border-radius:var(--r);font-family:var(--sans);
  font-size:.8rem;font-weight:600;cursor:pointer;border:none;transition:all .15s}
.btn-p{background:var(--cyan);color:#000}.btn-p:hover{background:var(--cyan2);color:#fff}
.btn-g{background:transparent;color:var(--t2);border:1px solid var(--b1)}
.btn-g:hover{border-color:var(--cyan);color:var(--cyan)}
.btn-sm{padding:6px 14px;font-size:.7rem}
.btns{display:flex;gap:10px;margin-top:6px;flex-wrap:wrap}

/* ── ALERTS ── */
.al{padding:12px 16px;border-radius:var(--r);font-size:.76rem;margin-bottom:14px;font-family:var(--mono)}
.al-ok {background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);color:var(--green)}
.al-err{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);color:var(--red)}
.al-inf{background:rgba(34,211,238,.07);border:1px solid rgba(34,211,238,.14);color:var(--cyan)}

/* ── TX LIST ── */
.trow{display:grid;grid-template-columns:30px 1fr auto;
  align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid rgba(30,42,56,.4)}
.trow:last-child{border-bottom:none}
.tic{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:.8rem;flex-shrink:0}
.tin {background:rgba(34,197,94,.12);color:var(--green)}
.tout{background:rgba(239,68,68,.1);color:var(--red)}
.tself{background:rgba(34,211,238,.08);color:var(--cyan)}
.tinfo{min-width:0}
.taddr{font-family:var(--mono);font-size:.7rem;color:var(--t2);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tmeta{font-size:.6rem;color:var(--t3);font-family:var(--mono);margin-top:1px}
.tamt{font-family:var(--mono);font-size:.78rem;font-weight:600;white-space:nowrap}
.tbadge{display:inline-block;padding:1px 6px;border-radius:4px;font-size:.56rem;
  font-family:var(--mono);margin-top:2px}
.badge-ok{background:rgba(34,197,94,.1);color:var(--green)}
.badge-pend{background:rgba(245,158,11,.1);color:var(--amber)}

/* ── QR ── */
.qrwrap{display:flex;flex-direction:column;align-items:center;gap:14px;padding:16px 0}
#qr-canvas{border:3px solid var(--cyan);border-radius:var(--r);background:#fff;padding:8px}
.addr-box{font-family:var(--mono);font-size:.7rem;color:var(--cyan);word-break:break-all;
  text-align:center;cursor:pointer;padding:10px 14px;background:var(--s2);
  border-radius:var(--r);border:1px solid var(--b1);max-width:440px;width:100%}
.addr-box:hover{border-color:var(--cyan)}

/* ── NETWORK STATS ── */
.nsgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;margin-bottom:16px}
.nscard{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);padding:12px;text-align:center}
.nsl{font-size:.57rem;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;font-family:var(--mono);margin-bottom:4px}
.nsv{font-size:1.05rem;font-weight:700;font-family:var(--mono);color:var(--t1)}

/* ── LEADERBOARD ── */
.lbrow{display:grid;grid-template-columns:22px 1fr 70px 50px 48px;
  align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid rgba(30,42,56,.4)}
.lbrow:last-child{border-bottom:none}

/* ── ADDR TABLE ── */
.arow{display:flex;align-items:center;gap:10px;padding:10px 0;
  border-bottom:1px solid rgba(30,42,56,.4)}
.arow:last-child{border-bottom:none}
.ainfo{flex:1;min-width:0}
.aa{font-family:var(--mono);font-size:.72rem;color:var(--cyan)}
.al2{font-size:.6rem;color:var(--t3);font-family:var(--mono);margin-top:2px}
.cpbtn{font-size:.6rem;padding:4px 10px;border-radius:5px;cursor:pointer;
  background:var(--s2);border:1px solid var(--b1);color:var(--t2);font-family:var(--mono)}
.cpbtn:hover{border-color:var(--cyan);color:var(--cyan)}

/* ── PREVIEW ── */
.preview-grid{display:grid;grid-template-columns:130px 1fr;gap:4px 12px;
  font-size:.72rem;color:var(--t2);font-family:var(--mono)}
.pk{color:var(--t3)}.pv{word-break:break-all}

/* ── FOOTER ── */
footer{border-top:1px solid var(--b1);padding:14px 24px;margin-top:6px;
  display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.fl{font-size:.6rem;color:var(--t3);font-family:var(--mono)}
.fl a{color:var(--cyan);text-decoration:none}
.fl a:hover{text-decoration:underline}
</style>
</head>
<body>

<nav>
  <a class="logo" href="https://polm.com.br" target="_blank">PoLM <em>/</em> Wallet</a>
  <span class="site">polm.com.br</span>
  <div class="pill net-pill" id="net-pill">mainnet</div>
  <div class="tabs">
    <div class="tab active"  onclick="pg('dashboard',this)">Dashboard</div>
    <div class="tab"         onclick="pg('send',this)">Send</div>
    <div class="tab"         onclick="pg('receive',this)">Receive</div>
    <div class="tab"         onclick="pg('history',this)">History</div>
    <div class="tab"         onclick="pg('addresses',this)">Addresses</div>
    <div class="tab"         onclick="pg('network',this)">Network</div>
  </div>
  <div class="nav-r">
    <span id="nstatus">connecting...</span>
  </div>
</nav>

<!-- DASHBOARD -->
<div class="page active" id="page-dashboard">
<div class="wrap">
  <div class="bgrid" id="bgrid"></div>
  <div class="sec">
    <div class="st">Recent activity</div>
    <div id="dash-txs"><p style="color:var(--t3);font-family:var(--mono);font-size:.75rem">Loading...</p></div>
  </div>
</div>
</div>

<!-- SEND -->
<div class="page" id="page-send">
<div class="wrap">
  <div class="sec">
    <div class="st">Send POLM</div>
    <div id="send-al"></div>
    <div class="fr">
      <label>From</label>
      <select class="fi" id="sfrom" onchange="updBal();updPreview()"></select>
    </div>
    <div style="margin-bottom:14px;font-size:.72rem;font-family:var(--mono)">
      Available: <span id="sbal" style="color:var(--cyan);font-weight:600">—</span> POLM
    </div>
    <div class="fr">
      <label>To address</label>
      <input class="fi" id="sto" placeholder="POLM...">
    </div>
    <div class="fh">
      <div class="fr">
        <label>Amount (POLM)</label>
        <input class="fi" id="samt" type="number" step="0.0001" min="0.0001" placeholder="0.0000">
      </div>
      <div class="fr">
        <label>Network fee</label>
        <input class="fi" id="sfee" type="number" step="0.0001" min="0.0001" value="0.001">
      </div>
    </div>
    <div class="fr">
      <label>Memo (optional)</label>
      <input class="fi" id="smemo" placeholder="Optional note — visible on chain">
    </div>
    <div class="btns">
      <button class="btn btn-p" onclick="doSend()">Send POLM</button>
      <button class="btn btn-g" onclick="clrSend()">Clear</button>
    </div>
  </div>
  <div class="sec">
    <div class="st">Preview</div>
    <div id="preview" style="color:var(--t3);font-family:var(--mono);font-size:.74rem">
      Fill in the form to preview transaction.
    </div>
  </div>
</div>
</div>

<!-- RECEIVE -->
<div class="page" id="page-receive">
<div class="wrap">
  <div class="sec">
    <div class="st">Receive POLM</div>
    <div class="fr">
      <label>Address</label>
      <select class="fi" id="raddr" onchange="drawQR()"></select>
    </div>
    <div class="qrwrap">
      <canvas id="qr-canvas" width="192" height="192"></canvas>
      <div class="addr-box" id="raddr-disp" onclick="cpAddr()">Select an address above</div>
      <button class="btn btn-g btn-sm" onclick="cpAddr()">Copy Address</button>
    </div>
  </div>
  <div class="sec">
    <div class="st">Generate new address</div>
    <div class="fh">
      <div class="fr">
        <label>Label</label>
        <input class="fi" id="nlabel" placeholder="e.g. Mining, Savings">
      </div>
      <div style="display:flex;align-items:flex-end;padding-bottom:14px">
        <button class="btn btn-p" onclick="newAddr()">Generate</button>
      </div>
    </div>
    <div id="newaddr-res"></div>
  </div>
</div>
</div>

<!-- HISTORY -->
<div class="page" id="page-history">
<div class="wrap">
  <div class="sec">
    <div class="st">Transaction history</div>
    <div class="fr" style="margin-bottom:14px">
      <label>Address</label>
      <select class="fi" id="haddr" onchange="loadHist()"></select>
    </div>
    <div id="hlist"><p style="color:var(--t3);font-family:var(--mono);font-size:.75rem">Select an address.</p></div>
  </div>
</div>
</div>

<!-- ADDRESSES -->
<div class="page" id="page-addresses">
<div class="wrap">
  <div class="sec">
    <div class="st">My addresses</div>
    <div id="alist"></div>
    <div style="margin-top:16px">
      <button class="btn btn-p btn-sm" onclick="pg('receive',document.querySelectorAll('.tab')[2])">
        New Address
      </button>
    </div>
  </div>
</div>
</div>

<!-- NETWORK -->
<div class="page" id="page-network">
<div class="wrap">
  <div class="sec">
    <div class="st">Node status</div>
    <div id="nsgrid" class="nsgrid"></div>
    <div class="fh">
      <div class="fr">
        <label>Node URL</label>
        <input class="fi" id="node-url-inp" placeholder="http://localhost:6060">
      </div>
      <div style="display:flex;align-items:flex-end;padding-bottom:14px">
        <button class="btn btn-p btn-sm" onclick="setNode()">Connect</button>
      </div>
    </div>
  </div>
  <div class="sec">
    <div class="st">Mining leaderboard</div>
    <div id="lboard"></div>
  </div>
</div>
</div>

<footer>
  <div class="fl">
    PoLM Wallet v1.2.0 &nbsp;·&nbsp;
    <a href="https://polm.com.br" target="_blank">polm.com.br</a> &nbsp;·&nbsp;
    MIT License
  </div>
  <div class="fl">
    <a href="/explorer" target="_blank">Explorer</a> &nbsp;·&nbsp;
    <a href="https://polm.com.br" target="_blank">Website</a>
  </div>
</footer>

<script>
const RC={DDR2:'#fb923c',DDR3:'#fbbf24',DDR4:'#22d3ee',DDR5:'#f87171'};
const B={DDR2:10,DDR3:8,DDR4:1,DDR5:0.5};
let addrs=[], nodeUrl='', net='mainnet';

function pg(id, el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(el) el.classList.add('active');
  if(id==='dashboard') loadDash();
  if(id==='history')   loadHist();
  if(id==='network')   loadNet();
  if(id==='addresses') loadAddrs();
  if(id==='receive')   populateSels();
}

async function api(path,method='GET',body=null){
  const o={method,headers:{'Content-Type':'application/json'}};
  if(body) o.body=JSON.stringify(body);
  const r=await fetch(path,o); return r.json();
}

async function init(){
  const i=await api('/wallet/info');
  addrs=i.addresses||[]; nodeUrl=i.node_url||''; net=i.network||'mainnet';
  document.getElementById('node-url-inp').value=nodeUrl;
  document.getElementById('net-pill').textContent=net;
  populateSels(); loadDash(); loadNodeStatus();
  setInterval(loadDash,12000); setInterval(loadNodeStatus,8000);
}

function populateSels(){
  ['sfrom','raddr','haddr'].forEach(id=>{
    const s=document.getElementById(id); if(!s) return;
    s.innerHTML=addrs.map(a=>
      `<option value="${a.address}">${a.label?a.label+': ':''}${a.address.slice(0,22)}...`
    ).join('');
  });
  updBal(); drawQR();
}

async function loadDash(){
  const grid=document.getElementById('bgrid');
  let html=''; let all=[];
  for(const a of addrs){
    const b=await api(`/wallet/balance/${a.address}`);
    const bal=(b.balance||0);
    html+=`<div class="bcard${bal>0?' sel':''}" onclick="selAddr('${a.address}')">
      <div class="bc-lbl">${a.label||'Account'}</div>
      <div class="bc-addr">${a.address}</div>
      <div class="bc-amt">${bal.toFixed(4)}<span class="bc-sym">POLM</span></div>
    </div>`;
    const h=await api(`/wallet/history/${a.address}`);
    if(Array.isArray(h)) all.push(...h.map(t=>({...t,_me:a.address})));
  }
  grid.innerHTML=html;
  all.sort((a,b)=>b.timestamp-a.timestamp);
  document.getElementById('dash-txs').innerHTML=txList(all.slice(0,15),null);
}

function txList(txs, me){
  if(!txs.length) return '<p style="color:var(--t3);font-family:var(--mono);font-size:.74rem;padding:10px 0">No transactions yet.</p>';
  return txs.map(tx=>{
    const my=me||tx._me;
    const isIn=tx.receiver===my, isSelf=tx.sender===my&&tx.receiver===my;
    const icon=isSelf?'⇄':isIn?'↓':'↑';
    const cls=isSelf?'tself':isIn?'tin':'tout';
    const col=isSelf?'var(--cyan)':isIn?'var(--green)':'var(--red)';
    const sign=isIn?'+':'-';
    const other=isIn?tx.sender:tx.receiver;
    return`<div class="trow">
      <div class="tic ${cls}">${icon}</div>
      <div class="tinfo">
        <div class="taddr">${other.slice(0,30)}...</div>
        <div class="tmeta">${fmtAge(tx.timestamp)}${tx.memo?' · '+tx.memo:''}</div>
      </div>
      <div style="text-align:right">
        <div class="tamt" style="color:${col}">${sign}${tx.amount.toFixed(4)} POLM</div>
        <span class="tbadge ${tx.confirmed?'badge-ok':'badge-pend'}">${tx.confirmed?'confirmed':'pending'}</span>
      </div>
    </div>`;
  }).join('');
}

function fmtAge(ts){
  const d=Math.floor(Date.now()/1000)-ts;
  if(d<60) return d+'s ago';
  if(d<3600) return Math.floor(d/60)+'m ago';
  if(d<86400) return Math.floor(d/3600)+'h ago';
  return new Date(ts*1000).toLocaleDateString();
}

async function updBal(){
  const a=document.getElementById('sfrom')?.value; if(!a) return;
  const b=await api(`/wallet/balance/${a}`);
  document.getElementById('sbal').textContent=(b.balance||0).toFixed(4);
}

function updPreview(){
  const from=document.getElementById('sfrom')?.value||'';
  const to=document.getElementById('sto')?.value||'';
  const amt=parseFloat(document.getElementById('samt')?.value)||0;
  const fee=parseFloat(document.getElementById('sfee')?.value)||0.001;
  const memo=document.getElementById('smemo')?.value||'';
  const total=(amt+fee).toFixed(4);
  document.getElementById('preview').innerHTML=`
    <div class="preview-grid">
      <span class="pk">From</span><span class="pv">${from||'—'}</span>
      <span class="pk">To</span><span class="pv">${to||'—'}</span>
      <span class="pk">Amount</span><span class="pv" style="color:var(--cyan)">${amt.toFixed(4)} POLM</span>
      <span class="pk">Network fee</span><span class="pv">${fee.toFixed(4)} POLM</span>
      <span class="pk">Total</span><span class="pv" style="color:var(--amber);font-weight:600">${total} POLM</span>
      ${memo?`<span class="pk">Memo</span><span class="pv">${memo}</span>`:''}
    </div>`;
}

['sfrom','sto','samt','sfee','smemo'].forEach(id=>{
  document.addEventListener('DOMContentLoaded',()=>{
    const el=document.getElementById(id);
    if(el) el.addEventListener('input',updPreview);
  });
});
document.addEventListener('DOMContentLoaded',()=>{
  const sf=document.getElementById('sfrom');
  if(sf) sf.addEventListener('change',()=>{updBal();updPreview();});
});

async function doSend(){
  const from=document.getElementById('sfrom').value;
  const to=document.getElementById('sto').value.trim();
  const amt=parseFloat(document.getElementById('samt').value);
  const fee=parseFloat(document.getElementById('sfee').value)||0.001;
  const memo=document.getElementById('smemo').value;
  const al=document.getElementById('send-al');

  if(!to.startsWith('POLM')||to.length<16){
    al.innerHTML='<div class="al al-err">Invalid recipient address — must start with POLM</div>';return;}
  if(!amt||amt<=0){al.innerHTML='<div class="al al-err">Enter a valid amount</div>';return;}

  al.innerHTML='<div class="al al-inf">Signing and broadcasting...</div>';
  try{
    const r=await api('/wallet/send','POST',{from,to,amount:amt,fee,memo});
    if(r.accepted){
      al.innerHTML=`<div class="al al-ok">Transaction sent!<br>
        <span style="font-size:.65rem;word-break:break-all">TX: ${r.tx_id}</span></div>`;
      ['sto','samt','smemo'].forEach(id=>document.getElementById(id).value='');
      document.getElementById('sfee').value='0.001';
      updBal(); updPreview();
    } else {
      al.innerHTML=`<div class="al al-err">Error: ${r.reason}</div>`;
    }
  }catch(e){al.innerHTML=`<div class="al al-err">Error: ${e.message}</div>`;}
}

function clrSend(){
  ['sto','samt','smemo'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('sfee').value='0.001';
  document.getElementById('send-al').innerHTML='';
  document.getElementById('preview').innerHTML='Fill in the form to preview transaction.';
}

function drawQR(){
  const addr=document.getElementById('raddr')?.value; if(!addr) return;
  document.getElementById('raddr-disp').textContent=addr;
  const cv=document.getElementById('qr-canvas');
  const ctx=cv.getContext('2d');
  const sz=192;
  ctx.fillStyle='#fff'; ctx.fillRect(0,0,sz,sz);
  // Pseudo-QR from address bytes
  const data=addr.split('').map(c=>c.charCodeAt(0));
  const cell=6;
  for(let i=0;i<data.length&&i<(sz/cell)*(sz/cell);i++){
    const x=(i%Math.floor(sz/cell))*cell;
    const y=Math.floor(i/Math.floor(sz/cell))*cell;
    ctx.fillStyle=data[i]%2===0?'#000':'#333';
    ctx.fillRect(x+0.5,y+0.5,cell-1,cell-1);
  }
  // Corner markers
  [[3,3],[sz-3-38,3],[3,sz-3-38]].forEach(([x,y])=>{
    ctx.fillStyle='#000'; ctx.fillRect(x,y,38,38);
    ctx.fillStyle='#fff'; ctx.fillRect(x+5,y+5,28,28);
    ctx.fillStyle='#000'; ctx.fillRect(x+10,y+10,18,18);
  });
}

function cpAddr(){
  const a=document.getElementById('raddr')?.value; if(!a) return;
  navigator.clipboard.writeText(a).then(()=>{
    const el=document.getElementById('raddr-disp');
    const orig=el.textContent; el.textContent='Copied!';
    setTimeout(()=>el.textContent=orig,1600);
  });
}

async function loadHist(){
  const a=document.getElementById('haddr')?.value; if(!a) return;
  const txs=await api(`/wallet/history/${a}`);
  document.getElementById('hlist').innerHTML=txList(Array.isArray(txs)?txs:[],a);
}

async function loadAddrs(){
  const list=document.getElementById('alist'); let html='';
  for(const a of addrs){
    const b=await api(`/wallet/balance/${a.address}`);
    html+=`<div class="arow">
      <div class="ainfo">
        <div class="aa">${a.address}</div>
        <div class="al2">${a.label||'No label'} &nbsp;·&nbsp; ${(b.balance||0).toFixed(4)} POLM &nbsp;·&nbsp; created ${a.created?new Date(a.created*1000).toLocaleDateString():'-'}</div>
      </div>
      <button class="cpbtn" onclick="navigator.clipboard.writeText('${a.address}')">Copy</button>
    </div>`;
  }
  list.innerHTML=html||'<p style="color:var(--t3);font-family:var(--mono)">No addresses.</p>';
}

async function newAddr(){
  const lbl=document.getElementById('nlabel').value.trim();
  const r=await api('/wallet/new_address','POST',{label:lbl});
  if(r.address){
    document.getElementById('newaddr-res').innerHTML=
      `<div class="al al-ok">New address generated:<br><span style="word-break:break-all">${r.address}</span></div>`;
    addrs=r.all; populateSels();
    document.getElementById('nlabel').value='';
  }
}

async function loadNodeStatus(){
  const s=await api('/wallet/node_status');
  if(!s||s.error){document.getElementById('nstatus').textContent='node offline';return;}
  document.getElementById('nstatus').textContent=`h=${s.height} ${s.network||''}`;
}

async function loadNet(){
  const s=await api('/wallet/node_status');
  const grid=document.getElementById('nsgrid');
  if(s&&!s.error&&grid){
    const rows=[
      ['Height',(s.height||0).toLocaleString()],
      ['Difficulty',s.difficulty],
      ['Reward',(s.next_reward||0).toFixed(2)+' POLM'],
      ['Epoch',s.epoch],
      ['Mempool',s.mempool_size||0],
      ['Peers',s.peers||0],
      ['Supply',Number(s.total_supply||0).toLocaleString('en',{maximumFractionDigits:0})],
      ['Block Time',s.block_time+'s'],
    ];
    grid.innerHTML=rows.map(([l,v])=>
      `<div class="nscard"><div class="nsl">${l}</div><div class="nsv">${v}</div></div>`
    ).join('');
  }
  const m=await api('/wallet/miners');
  const lb=document.getElementById('lboard'); if(!lb) return;
  const miners=Object.entries(m||{}).sort((a,b)=>b[1].blocks-a[1].blocks);
  const total=miners.reduce((s,[,v])=>s+v.blocks,0);
  if(!miners.length){lb.innerHTML='<p style="color:var(--t3);font-family:var(--mono)">No miners yet.</p>';return;}
  const rankCol=['#fbbf24','#9ca3af','#cd7f32'];
  lb.innerHTML=miners.map(([id,v],i)=>{
    const pct=total?(v.blocks/total*100):0;
    const col=RC[v.ram]||'#22d3ee';
    return`<div class="lbrow">
      <span style="font-family:var(--mono);font-size:.68rem;color:${rankCol[i]||'var(--t3)'};">#${i+1}</span>
      <div>
        <div style="font-family:var(--mono);font-size:.7rem;color:${col};white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${id.slice(0,26)}...</div>
        <div style="font-size:.58rem;color:var(--t3);font-family:var(--mono)">${v.ram} · ${(v.avg_latency||0).toFixed(0)}ns · ${B[v.ram]||1}× boost</div>
      </div>
      <div>
        <div style="height:3px;background:var(--s3);border-radius:2px">
          <div style="height:100%;width:${Math.min(pct,100).toFixed(1)}%;background:${col};border-radius:2px"></div>
        </div>
        <div style="font-size:.58rem;color:var(--t3);font-family:var(--mono);text-align:right;margin-top:1px">${pct.toFixed(1)}%</div>
      </div>
      <div style="font-family:var(--mono);font-size:.72rem;color:var(--cyan);text-align:right">${v.blocks}</div>
      <div style="font-family:var(--mono);font-size:.72rem;color:var(--green);text-align:right">${(v.reward||0).toFixed(0)}</div>
    </div>`;
  }).join('');
}

function selAddr(addr){
  document.getElementById('sfrom').value=addr;
  pg('send',document.querySelectorAll('.tab')[1]);
  updBal(); updPreview();
}

async function setNode(){
  const url=document.getElementById('node-url-inp').value.trim();
  const r=await api('/wallet/set_node','POST',{url});
  if(r.ok){nodeUrl=url; loadNodeStatus();}
}

init();
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
