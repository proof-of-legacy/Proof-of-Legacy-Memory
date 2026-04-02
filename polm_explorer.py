"""
PoLM Explorer  v2.2.0  —  Professional Edition
https://polm.com.br

Dashboard · Ranking · Blocks · Protocol
Founder : @aluisiofer  |  Project : @polm2026
"""

from flask import Flask, render_template_string, jsonify, request, Response
import json, time, urllib.request

VERSION   = "2.2.0"
WEBSITE   = "https://polm.com.br"
GITHUB    = "https://github.com/proof-of-legacy/Proof-of-Legacy-Memory"
TWITTER_P = "https://x.com/polm2026"
TWITTER_F = "https://x.com/aluisiofer"
GENESIS   = "975329dc93db37c7b61d7288f8f57e6b8c2e5c0d4a82f1e93b0c6d5a7e4f2b1"

BLOCK_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Block #{{ height }} — PoLM Explorer</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#05070a;--s1:#0b0e14;--b1:#1a2332;--cyan:#00e5ff;--green:#00e676;--amber:#ffab00;--t1:#e8f0f8;--t2:#7090a8;--t3:#2d4055;--mono:'JetBrains Mono',monospace;--sans:'Syne',sans-serif}
body{background:var(--bg);color:var(--t1);font-family:var(--sans);padding:24px 18px}
nav{background:rgba(5,7,10,.98);border-bottom:1px solid var(--b1);height:54px;display:flex;align-items:center;padding:0 24px;gap:14px;position:fixed;top:0;left:0;right:0;z-index:99;backdrop-filter:blur(16px)}
.logo{font-family:var(--mono);font-weight:700;color:var(--cyan);font-size:.95rem;text-decoration:none}
.back{font-family:var(--mono);font-size:.72rem;color:var(--t2);text-decoration:none;border:1px solid var(--b1);padding:5px 12px;border-radius:6px;margin-left:auto}
.back:hover{color:var(--cyan);border-color:var(--cyan)}
.wrap{max-width:900px;margin:70px auto 0}
h1{font-family:var(--mono);font-size:1.2rem;color:var(--cyan);margin-bottom:18px}
.card{background:var(--s1);border:1px solid var(--b1);border-radius:12px;overflow:hidden}
.row{display:grid;grid-template-columns:160px 1fr;border-bottom:1px solid rgba(26,35,50,.5);padding:12px 18px}
.row:last-child{border-bottom:none}
.rk{font-family:var(--mono);font-size:.68rem;color:var(--t3);text-transform:uppercase;letter-spacing:.08em;align-self:center}
.rv{font-family:var(--mono);font-size:.78rem;color:var(--t1);word-break:break-all}
.rv.cyan{color:var(--cyan)}.rv.amber{color:var(--amber)}.rv.green{color:var(--green)}
footer{margin-top:20px;text-align:center;font-size:.62rem;color:var(--t3);font-family:var(--mono)}
footer a{color:var(--cyan);text-decoration:none}
</style>
</head>
<body>
<nav>
  <a class="logo" href="/">PoLM / Explorer</a>
  <a class="back" href="/">← Back to Explorer</a>
</nav>
<div class="wrap">
  <h1>Block #{{ height }}</h1>
  <div class="card">
    {% for key, val, col in rows %}
    <div class="row">
      <div class="rk">{{ key }}</div>
      <div class="rv {{ col }}">{{ val }}</div>
    </div>
    {% endfor %}
  </div>
  <footer style="margin-top:20px">
    <a href="https://polm.com.br">polm.com.br</a> &nbsp;·&nbsp;
    <a href="https://x.com/polm2026">@polm2026</a> &nbsp;·&nbsp;
    PoLM Explorer v{{ version }}
  </footer>
</div>
</body>
</html>"""


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PoLM Explorer — polm.com.br</title>
<meta name="description" content="PoLM Blockchain Explorer — Proof of Legacy Memory. Live stats, mining leaderboard, block explorer. Any RAM mines.">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Syne:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#05070a;--s1:#0b0e14;--s2:#0f1520;--s3:#080b10;
  --b1:#1a2332;--b2:#223044;
  --cyan:#00e5ff;--cyan2:#0097a7;--green:#00e676;--amber:#ffab00;
  --orange:#ff6d00;--purple:#d500f9;--red:#ff1744;
  --t1:#e8f0f8;--t2:#7090a8;--t3:#2d4055;
  --mono:'JetBrains Mono',monospace;--sans:'Syne',sans-serif;
  --r:8px;--r2:12px
}
html{font-size:13px;scroll-behavior:smooth}
body{
  background:var(--bg);color:var(--t1);font-family:var(--sans);
  background-image:radial-gradient(ellipse 80% 40% at 50% -5%,rgba(0,229,255,.05) 0%,transparent 65%)
}

/* ── NAV ── */
nav{
  background:rgba(5,7,10,.98);border-bottom:1px solid var(--b1);
  height:54px;display:flex;align-items:center;padding:0 24px;gap:14px;
  position:sticky;top:0;z-index:999;backdrop-filter:blur(16px)
}
.logo{font-family:var(--mono);font-weight:700;font-size:.95rem;color:var(--cyan);letter-spacing:.06em;white-space:nowrap;text-decoration:none}
.logo em{color:var(--t3);font-style:normal;font-weight:300}
.site{font-size:.6rem;color:var(--t3);font-family:var(--mono);border-left:1px solid var(--b1);padding-left:12px;white-space:nowrap}
.pill{padding:3px 10px;border-radius:20px;font-size:.6rem;font-family:var(--mono);font-weight:500}
.pill-net{background:rgba(0,230,118,.08);border:1px solid rgba(0,230,118,.18);color:var(--green);display:flex;align-items:center;gap:5px}
.pill-net::before{content:'';width:5px;height:5px;border-radius:50%;background:var(--green);animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.nav-tabs{display:flex;gap:2px;margin-left:8px}
.tab{padding:5px 13px;border-radius:6px;font-size:.7rem;cursor:pointer;color:var(--t2);border:1px solid transparent;transition:all .15s;font-family:var(--mono)}
.tab:hover{color:var(--t1);background:var(--s2)}
.tab.active{color:var(--cyan);background:rgba(0,229,255,.07);border-color:rgba(0,229,255,.15)}
.nav-right{margin-left:auto;display:flex;align-items:center;gap:8px}
#ts{font-size:.6rem;color:var(--t3);font-family:var(--mono)}
.rbtn{background:transparent;border:1px solid var(--b1);color:var(--t2);padding:5px 12px;border-radius:6px;cursor:pointer;font-family:var(--mono);font-size:.65rem;transition:all .15s}
.rbtn:hover{border-color:var(--cyan);color:var(--cyan)}

/* ── PAGES ── */
.page{display:none;max-width:1480px;margin:0 auto;padding:20px 18px}
.page.active{display:block}

/* ── SEARCH ── */
.sbar{display:flex;gap:8px;margin-bottom:20px;max-width:580px}
.sbar input{flex:1;background:var(--s1);border:1px solid var(--b1);border-radius:var(--r);padding:9px 14px;color:var(--t1);font-family:var(--mono);font-size:.8rem;outline:none;transition:border-color .15s}
.sbar input:focus{border-color:var(--cyan)}
.sbar input::placeholder{color:var(--t3)}
.sbar button{background:var(--cyan);border:none;color:#000;padding:9px 18px;border-radius:var(--r);cursor:pointer;font-family:var(--sans);font-size:.75rem;font-weight:700;transition:all .15s}
.sbar button:hover{filter:brightness(1.1)}

/* ── STAT CARDS ── */
.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:8px;margin-bottom:18px}
.sc{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:14px;position:relative;overflow:hidden;transition:border-color .15s}
.sc::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--ac,var(--cyan));opacity:.6}
.sc:hover{border-color:var(--b2)}
.sc-l{font-size:.58rem;color:var(--t3);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px;font-family:var(--mono)}
.sc-v{font-size:1.2rem;font-weight:700;color:var(--t1);font-family:var(--mono);line-height:1.1}
.sc-s{font-size:.6rem;color:var(--t3);margin-top:3px;font-family:var(--mono)}

/* ── SECTIONS ── */
.sec{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:18px;margin-bottom:14px}
.st{font-size:.6rem;font-weight:600;letter-spacing:.15em;text-transform:uppercase;color:var(--t2);margin-bottom:14px;display:flex;align-items:center;gap:8px;font-family:var(--mono)}
.st::after{content:'';flex:1;height:1px;background:var(--b1)}
.st span{color:var(--t3);font-size:.58rem;font-weight:400;letter-spacing:0;text-transform:none;margin-left:4px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
@media(max-width:900px){.two{grid-template-columns:1fr}}

/* ── SUPPLY ── */
.sup-wrap{margin-top:8px}
.sup-row{display:flex;justify-content:space-between;font-size:.75rem;font-family:var(--mono);margin-bottom:5px}
.sup-bar{height:6px;background:var(--s3);border-radius:3px;overflow:hidden;margin:4px 0 8px}
.sup-fill{height:100%;background:linear-gradient(90deg,var(--cyan2),var(--cyan));border-radius:3px;transition:width 1s}
.sup-meta{display:flex;justify-content:space-between;font-size:.6rem;color:var(--t3);font-family:var(--mono)}

/* ── LEADERBOARD ── */
.lb-hdr{display:grid;grid-template-columns:28px 1fr 90px 60px 70px 80px;gap:8px;padding:0 0 8px;border-bottom:1px solid var(--b1);margin-bottom:4px}
.lb-hdr span{font-size:.58rem;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;font-family:var(--mono)}
.lb-hdr span:not(:nth-child(2)){text-align:right}
.lb-hdr span:nth-child(2){text-align:left}
.lrow{display:grid;grid-template-columns:28px 1fr 90px 60px 70px 80px;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid rgba(26,35,50,.5);transition:background .1s}
.lrow:last-child{border-bottom:none}
.lrow:hover{background:rgba(0,229,255,.02)}
.rnk{font-family:var(--mono);font-size:.72rem;font-weight:700;color:var(--t3);text-align:center}
.rnk.r1{color:#ffab00}.rnk.r2{color:#9ca3af}.rnk.r3{color:#cd7f32}
.minfo{min-width:0}
.maddr{font-family:var(--mono);font-size:.72rem;color:var(--cyan);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
.maddr:hover{text-decoration:underline}
.mmeta{font-size:.6rem;color:var(--t3);margin-top:2px;font-family:var(--mono);display:flex;align-items:center;gap:6px}
.bar-wrap{position:relative;height:4px;background:var(--s3);border-radius:2px;overflow:hidden}
.bar-fill{height:100%;border-radius:2px;transition:width .6s}
.num{font-family:var(--mono);font-size:.72rem;text-align:right;white-space:nowrap}
.gc{color:var(--green)}.ac{color:var(--amber)}.cc{color:var(--cyan)}.mc{color:var(--t3)}.rc{color:var(--red)}

/* ── RAM BADGES ── */
.ram{display:inline-block;padding:2px 7px;border-radius:4px;font-size:.6rem;font-weight:700;font-family:var(--mono)}
.ddr2{background:rgba(255,171,0,.1);color:#ffab00;border:1px solid rgba(255,171,0,.2)}
.ddr3{background:rgba(0,230,118,.08);color:#00e676;border:1px solid rgba(0,230,118,.18)}
.ddr4{background:rgba(0,229,255,.07);color:var(--cyan);border:1px solid rgba(0,229,255,.15)}
.ddr5{background:rgba(213,0,249,.08);color:#d500f9;border:1px solid rgba(213,0,249,.15)}

/* ── ANY RAM CARDS ── */
.ram-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
@media(max-width:600px){.ram-grid{grid-template-columns:repeat(2,1fr)}}
.rc{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);padding:14px;text-align:center;transition:border-color .15s;position:relative;overflow:hidden}
.rc::after{content:'';position:absolute;bottom:0;left:0;right:0;height:2px}
.rc-ddr2::after{background:linear-gradient(90deg,#ff6d00,#ffab00)}
.rc-ddr3::after{background:linear-gradient(90deg,#00e676,#00bfa5)}
.rc-ddr4::after{background:linear-gradient(90deg,var(--cyan),var(--cyan2))}
.rc-ddr5::after{background:linear-gradient(90deg,#d500f9,#aa00ff)}
.rc:hover{border-color:var(--b2)}
.rc-t{font-family:var(--mono);font-size:.9rem;font-weight:700;margin-bottom:4px}
.rc-ddr2 .rc-t{color:#ffab00}.rc-ddr3 .rc-t{color:#00e676}
.rc-ddr4 .rc-t{color:var(--cyan)}.rc-ddr5 .rc-t{color:#d500f9}
.rc-lat{font-size:.6rem;color:var(--t3);font-family:var(--mono);margin-bottom:8px;line-height:1.6}
.rc-tag{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.6rem;font-family:var(--mono);font-weight:700;background:rgba(0,230,118,.1);color:var(--green);border:1px solid rgba(0,230,118,.2)}

/* ── BLOCKS TABLE ── */
table{width:100%;border-collapse:collapse;font-size:.72rem}
th{text-align:left;padding:7px 10px;color:var(--t3);font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;border-bottom:1px solid var(--b1);font-family:var(--mono);font-weight:400;white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid rgba(26,35,50,.4);vertical-align:middle;font-family:var(--mono)}
tbody tr{cursor:pointer;transition:background .1s}
tbody tr:hover td{background:rgba(0,229,255,.02)}
tbody tr:last-child td{border-bottom:none}
a.hl{color:var(--cyan);text-decoration:none}
a.hl:hover{text-decoration:underline}

/* ── INFO ROWS ── */
.irow{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid rgba(26,35,50,.4);font-size:.75rem}
.irow:last-child{border-bottom:none}
.ik{color:var(--t3);font-family:var(--mono)}.iv{color:var(--t1);font-family:var(--mono);font-weight:500}

/* ── RANKING ── */
.rank-hero{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:24px;margin-bottom:14px;text-align:center}
.rank-hero h2{font-size:1.2rem;font-weight:700;margin-bottom:6px;font-family:var(--mono);color:var(--cyan)}
.rank-hero p{font-size:.75rem;color:var(--t2);font-family:var(--mono)}
.podium{display:grid;grid-template-columns:1fr 1.1fr 1fr;gap:12px;margin:20px 0;align-items:end}
@media(max-width:600px){.podium{grid-template-columns:1fr}}
.pod{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r2);padding:16px;text-align:center;transition:all .2s}
.pod:hover{transform:translateY(-2px)}
.pod.p1{border-color:rgba(255,171,0,.3);background:rgba(255,171,0,.04)}
.pod.p2{border-color:rgba(156,163,175,.2)}
.pod.p3{border-color:rgba(205,127,50,.2)}
.pod-rank{font-size:1.8rem;margin-bottom:8px}
.pod-addr{font-family:var(--mono);font-size:.68rem;color:var(--cyan);margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pod-blocks{font-family:var(--mono);font-size:1.6rem;font-weight:700}
.pod-pct{font-size:.7rem;color:var(--t3);font-family:var(--mono)}
.pod-polm{font-size:.8rem;color:var(--green);font-family:var(--mono);margin-top:4px}
.pod-ram{margin-top:6px}
.rank-hdr{display:grid;grid-template-columns:28px 1fr 80px 70px 70px 90px 60px;gap:8px;padding:6px 0 8px;border-bottom:1px solid var(--b1);margin-bottom:4px}
.rank-hdr span{font-size:.57rem;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;font-family:var(--mono)}
.rank-hdr span:not(:nth-child(2)){text-align:right}
.rank-hdr span:nth-child(2){text-align:left}
.rrow{display:grid;grid-template-columns:28px 1fr 80px 70px 70px 90px 60px;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid rgba(26,35,50,.4);transition:background .1s}
.rrow:last-child{border-bottom:none}
.rrow:hover{background:rgba(0,229,255,.02)}

/* ── EPOCH TABLE ── */
.epoch-table{width:100%;border-collapse:collapse}
.epoch-table th{text-align:left;padding:8px 12px;font-size:.58rem;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;font-family:var(--mono);border-bottom:1px solid var(--b1);font-weight:400}
.epoch-table td{padding:10px 12px;border-bottom:1px solid rgba(26,35,50,.35);font-family:var(--mono);font-size:.8rem}
.epoch-table tr:last-child td{border-bottom:none}
.epoch-table .ep-now td{background:rgba(0,229,255,.03)}

/* ── GENESIS ── */
.genesis-card{background:var(--s2);border:1px solid rgba(0,229,255,.15);border-radius:var(--r2);padding:16px;margin-bottom:14px}
.genesis-label{font-size:.6rem;color:var(--t3);font-family:var(--mono);text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px}
.genesis-hash{font-family:var(--mono);font-size:.75rem;color:var(--cyan);word-break:break-all;line-height:1.5}

/* ── FORMULA BOX ── */
.formula-box{background:var(--s3);border:1px solid var(--b1);border-radius:var(--r2);padding:20px 24px;text-align:center;margin-bottom:14px}
.formula-eq{font-family:var(--mono);font-size:1.1rem;color:var(--cyan);font-weight:700;margin-bottom:8px}
.formula-note{font-family:var(--mono);font-size:.72rem;color:var(--t2);line-height:2}

/* ── FOOTER ── */
footer{border-top:1px solid var(--b1);padding:14px 24px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-top:8px}
.fl{font-size:.6rem;color:var(--t3);font-family:var(--mono)}
.fl a{color:var(--cyan);text-decoration:none}
.fl a:hover{text-decoration:underline}
</style>
</head>
<body>
<nav>
  <a class="logo" href="/">PoLM <em>/</em> Explorer</a>
  <span class="site">polm.com.br</span>
  <div class="pill pill-net" id="net-pill">mainnet</div>
  <div class="nav-tabs">
    <div class="tab active" onclick="show('dashboard',this)">Dashboard</div>
    <div class="tab" onclick="show('ranking',this)">Ranking</div>
    <div class="tab" onclick="show('blocks',this)">Blocks</div>
    <div class="tab" onclick="show('protocol',this)">Protocol</div>
  </div>
  <div class="nav-right">
    <span id="ts"></span>
    <button class="rbtn" onclick="load()">↻ refresh</button>
  </div>
</nav>

<!-- ── DASHBOARD ── -->
<div class="page active" id="page-dashboard">
<div style="max-width:1480px;margin:0 auto;padding:20px 18px">
  <div class="sbar">
    <input id="q" placeholder="Search block height or hash (64 chars)…" onkeydown="if(event.key==='Enter')go()">
    <button onclick="go()">Search</button>
  </div>
  <div class="sgrid" id="sg"></div>
  <div class="sec">
    <div class="st">Supply <span id="spct"></span></div>
    <div class="sup-wrap">
      <div class="sup-row"><span id="sm" style="color:var(--cyan)"></span><span style="color:var(--t3)">/ 210,000,000 POLM max supply</span></div>
      <div class="sup-bar"><div class="sup-fill" id="sb" style="width:0%"></div></div>
      <div class="sup-meta"><span id="spct2"></span><span>epoch halving · 50.0 POLM initial reward · score = 1/latency_ns</span></div>
    </div>
  </div>
  <div class="two">
    <div class="sec">
      <div class="st">Live leaderboard <span id="lb-count"></span></div>
      <div class="lb-hdr"><span>#</span><span>Miner</span><span>Share</span><span>Blocks</span><span>POLM</span><span>Latency</span></div>
      <div id="lb"></div>
    </div>
    <div>
      <div class="sec" style="margin-bottom:14px">
        <div class="st">Network</div>
        <div id="ni"></div>
      </div>
      <div class="sec">
        <div class="st">Any RAM mines</div>
        <div class="ram-grid">
          <div class="rc rc-ddr2">
            <div class="rc-t">DDR2</div>
            <div class="rc-lat">~3500–8000 ns<br>High latency = high score/step</div>
            <div class="rc-tag">✓ Mines now</div>
          </div>
          <div class="rc rc-ddr3">
            <div class="rc-t">DDR3</div>
            <div class="rc-lat">~1500–4000 ns<br>Balanced latency profile</div>
            <div class="rc-tag">✓ Mines now</div>
          </div>
          <div class="rc rc-ddr4">
            <div class="rc-t">DDR4</div>
            <div class="rc-lat">~900–1900 ns<br>Lower latency = more nonces</div>
            <div class="rc-tag">✓ Mines now</div>
          </div>
          <div class="rc rc-ddr5">
            <div class="rc-t">DDR5</div>
            <div class="rc-lat">~500–900 ns<br>Fastest throughput</div>
            <div class="rc-tag">✓ Mines now</div>
          </div>
        </div>
        <div style="margin-top:12px;padding:10px 14px;background:rgba(0,229,255,.04);border-radius:8px;border:1px solid rgba(0,229,255,.1)">
          <span style="font-family:var(--mono);font-size:.72rem;color:var(--t2)">
            Score = <span style="color:var(--cyan)">1 / latency_ns</span> — no artificial boost, no penalty. Physics only.
          </span>
        </div>
      </div>
    </div>
  </div>
  <div class="sec">
    <div class="st">Latest blocks <span id="blk-count"></span></div>
    <table><thead><tr><th>Height</th><th>Hash</th><th>Miner</th><th>RAM</th><th>Latency</th><th>Score</th><th>Nonce</th><th>Reward</th><th>Age</th></tr></thead>
    <tbody id="bt"></tbody></table>
  </div>
</div>
</div>

<!-- ── RANKING ── -->
<div class="page" id="page-ranking">
<div style="max-width:1480px;margin:0 auto;padding:20px 18px">
  <div class="rank-hero">
    <h2>⛏ Mining Leaderboard</h2>
    <p>Ranked by blocks mined · Updated every 8s · Any RAM competes — latency is the only judge</p>
  </div>
  <div class="podium" id="podium"></div>
  <div class="sec">
    <div class="st">Full rankings</div>
    <div class="rank-hdr"><span>#</span><span>Miner</span><span>Share</span><span>Blocks</span><span>POLM</span><span>Avg Latency</span><span>RAM</span></div>
    <div id="full-rank"></div>
  </div>
  <div class="sec">
    <div class="st">How scoring works</div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
      <div style="background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);padding:14px;text-align:center">
        <div style="font-family:var(--mono);font-size:.65rem;color:var(--t3);margin-bottom:6px">SCORE FORMULA</div>
        <div style="font-family:var(--mono);font-size:.95rem;color:var(--cyan);font-weight:700">1 / latency_ns</div>
      </div>
      <div style="background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);padding:14px;text-align:center">
        <div style="font-family:var(--mono);font-size:.65rem;color:var(--t3);margin-bottom:6px">MAX THREADS</div>
        <div style="font-family:var(--mono);font-size:.95rem;color:var(--amber);font-weight:700">4 per miner</div>
      </div>
      <div style="background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);padding:14px;text-align:center">
        <div style="font-family:var(--mono);font-size:.65rem;color:var(--t3);margin-bottom:6px">WALK STEPS</div>
        <div style="font-family:var(--mono);font-size:.95rem;color:var(--green);font-weight:700">100,000 / nonce</div>
      </div>
    </div>
  </div>
</div>
</div>

<!-- ── BLOCKS ── -->
<div class="page" id="page-blocks">
<div style="max-width:1480px;margin:0 auto;padding:20px 18px">
  <div class="genesis-card">
    <div class="genesis-label">Genesis block — block #0</div>
    <div class="genesis-hash" id="genesis-hash">—</div>
    <div style="font-size:.62rem;color:var(--t3);font-family:var(--mono);margin-top:6px">"Any RAM mines. Latency is truth." — PoLM Genesis, March 2026, polm.com.br</div>
  </div>
  <div class="sec">
    <div class="st">All blocks <span id="all-blk-count"></span></div>
    <table><thead><tr><th>Height</th><th>Hash</th><th>Miner</th><th>RAM</th><th>Latency</th><th>Score</th><th>Nonce</th><th>Reward</th><th>Age</th></tr></thead>
    <tbody id="all-bt"></tbody></table>
    <div style="text-align:center;margin-top:14px"><button class="rbtn" onclick="loadMore()">Load more</button></div>
  </div>
</div>
</div>

<!-- ── PROTOCOL ── -->
<div class="page" id="page-protocol">
<div style="max-width:1480px;margin:0 auto;padding:20px 18px">

  <div class="formula-box">
    <div class="formula-eq">score = 1 / latency_ns</div>
    <div class="formula-note">
      No boost multiplier. No penalty. Pure physics.<br>
      Slower RAM → higher latency → higher score per step → valid block<br>
      Faster RAM → lower latency → more nonces per second → valid block
    </div>
  </div>

  <div class="two">
    <div class="sec"><div class="st">Protocol parameters</div><div id="proto-net"></div></div>
    <div class="sec">
      <div class="st">Algorithm</div>
      <div class="irow"><span class="ik">Score formula</span><span class="iv" style="color:var(--cyan)">1 / latency_ns</span></div>
      <div class="irow"><span class="ik">Boost multiplier</span><span class="iv" style="color:var(--green)">None — pure latency</span></div>
      <div class="irow"><span class="ik">Thread penalty</span><span class="iv" style="color:var(--green)">None — max 4 threads</span></div>
      <div class="irow"><span class="ik">DAG (Epoch 0)</span><span class="iv">256 MB — doubles each epoch</span></div>
      <div class="irow"><span class="ik">Walk steps</span><span class="iv">100,000 per nonce</span></div>
      <div class="irow"><span class="ik">Hash function</span><span class="iv">SHA3-256</span></div>
      <div class="irow"><span class="ik">Signatures</span><span class="iv">ECDSA secp256k1</span></div>
      <div class="irow"><span class="ik">Coin type</span><span class="iv">SLIP-44 #637</span></div>
    </div>
  </div>

  <div class="sec">
    <div class="st">Any RAM mines — all generations welcome</div>
    <div class="ram-grid">
      <div class="rc rc-ddr2">
        <div class="rc-t">DDR2</div>
        <div class="rc-lat">~3500–8000 ns avg latency<br>High latency → high score/step<br>Any PC from 2004–2010</div>
        <div class="rc-tag">✓ Mines now</div>
      </div>
      <div class="rc rc-ddr3">
        <div class="rc-t">DDR3</div>
        <div class="rc-lat">~1500–4000 ns avg latency<br>Balanced latency profile<br>Mainstream PCs 2010–2016</div>
        <div class="rc-tag">✓ Mines now</div>
      </div>
      <div class="rc rc-ddr4">
        <div class="rc-t">DDR4</div>
        <div class="rc-lat">~900–1900 ns avg latency<br>More nonces per second<br>Modern standard 2016–2022</div>
        <div class="rc-tag">✓ Mines now</div>
      </div>
      <div class="rc rc-ddr5">
        <div class="rc-t">DDR5</div>
        <div class="rc-lat">~500–900 ns avg latency<br>Highest nonce throughput<br>Latest hardware 2022+</div>
        <div class="rc-tag">✓ Mines now</div>
      </div>
    </div>
  </div>

  <div class="sec">
    <div class="st">Epoch schedule — DAG doubles, reward halves</div>
    <table class="epoch-table">
      <thead>
        <tr><th>Epoch</th><th>Blocks</th><th>~Days</th><th>DAG</th><th>Min RAM</th><th>Reward</th><th>Who mines?</th></tr>
      </thead>
      <tbody>
        <tr class="ep-now">
          <td style="color:var(--cyan);font-weight:700">0 ← NOW</td>
          <td>0 – 100k</td><td>~138d</td>
          <td style="color:var(--cyan)">256 MB</td><td style="color:var(--green);font-weight:700">4 GB</td>
          <td style="color:var(--green);font-weight:700">50 POLM</td>
          <td>Any PC with 4 GB+ RAM</td>
        </tr>
        <tr><td>1</td><td>100k – 200k</td><td>~138d</td><td>512 MB</td><td>16 GB</td><td>50 POLM</td><td>Most modern desktops</td></tr>
        <tr><td>2</td><td>200k – 300k</td><td>~138d</td><td>1 GB</td><td>32 GB</td><td>25 POLM</td><td>High-end workstations</td></tr>
        <tr><td>3</td><td>300k – 400k</td><td>~138d</td><td>2 GB</td><td>64 GB</td><td>12.5 POLM</td><td>Server-class machines</td></tr>
        <tr><td>4</td><td>400k – 500k</td><td>~138d</td><td>4 GB</td><td>128 GB</td><td>6.25 POLM</td><td>Dedicated RAM rigs</td></tr>
        <tr><td>5</td><td>500k – 600k</td><td>~138d</td><td>8 GB</td><td>256 GB</td><td>3.12 POLM</td><td>Enterprise RAM servers</td></tr>
        <tr><td>6</td><td>600k – 700k</td><td>~138d</td><td>16 GB</td><td>512 GB</td><td>1.56 POLM</td><td>RAM mining boards</td></tr>
        <tr><td style="color:var(--amber)">7 ⚡</td><td>700k – 800k</td><td>~138d</td><td style="color:var(--amber)">32 GB</td><td style="color:var(--amber)">1 TB</td><td>0.78 POLM</td><td style="color:var(--amber)">Industrial RAM arrays!</td></tr>
        <tr><td style="color:var(--red)">8+ 🏭</td><td>800k+</td><td>—</td><td style="color:var(--red)">64 GB+</td><td style="color:var(--red)">2 TB+</td><td>0.39 POLM</td><td style="color:var(--red)">New hardware industry</td></tr>
      </tbody>
    </table>
  </div>

  <div class="sec">
    <div class="st">Links</div>
    <div class="irow"><span class="ik">Website</span><a class="iv hl" href="https://polm.com.br" target="_blank">polm.com.br</a></div>
    <div class="irow"><span class="ik">GitHub</span><a class="iv hl" href="https://github.com/proof-of-legacy/Proof-of-Legacy-Memory" target="_blank">proof-of-legacy/Proof-of-Legacy-Memory</a></div>
    <div class="irow"><span class="ik">Project Twitter</span><a class="iv hl" href="https://x.com/polm2026" target="_blank">@polm2026</a></div>
    <div class="irow"><span class="ik">Founder</span><a class="iv hl" href="https://x.com/aluisiofer" target="_blank">@aluisiofer (Aluísio Fernandes — Aluminium)</a></div>
    <div class="irow"><span class="ik">Polygon Token</span><a class="iv hl" href="https://polygonscan.com/token/0x79175931C54c9765E5846229a0eB118ef24fdE55" target="_blank">0x79175931...fdE55</a></div>
    <div class="irow"><span class="ik">Claim POLM</span><a class="iv hl" href="https://polm.com.br/claim" target="_blank">polm.com.br/claim</a></div>
    <div class="irow"><span class="ik">Roadmap</span><a class="iv hl" href="https://polm.com.br/roadmap" target="_blank">polm.com.br/roadmap</a></div>
    <div class="irow"><span class="ik">Node API</span><a class="iv hl" href="https://polm.com.br/api/" target="_blank">polm.com.br/api/</a></div>
  </div>
</div>
</div>

<footer>
  <div class="fl">PoLM Explorer v2.2.0 &nbsp;·&nbsp; <a href="https://polm.com.br">polm.com.br</a> &nbsp;·&nbsp; MIT License &nbsp;·&nbsp; Mainnet &nbsp;·&nbsp; score = 1/latency_ns</div>
  <div class="fl"><a href="https://x.com/polm2026" target="_blank">@polm2026</a> &nbsp;·&nbsp; <a href="https://x.com/aluisiofer" target="_blank">@aluisiofer</a> &nbsp;·&nbsp; <a href="https://github.com/proof-of-legacy/Proof-of-Legacy-Memory" target="_blank">GitHub</a></div>
</footer>

<script>
const RC={DDR2:'#ffab00',DDR3:'#00e676',DDR4:'#00e5ff',DDR5:'#d500f9'};
const MEDALS=['🥇','🥈','🥉'];
const RK=['#ffab00','#9ca3af','#cd7f32'];
let blkOffset=0;

function show(id,el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(el) el.classList.add('active');
  if(id==='ranking') loadRanking();
  if(id==='blocks')  loadAllBlocks();
  if(id==='protocol') loadProto();
}

function go(){
  const q=document.getElementById('q').value.trim();
  if(!q) return;
  if(/^\d+$/.test(q)) location='/block/'+q;
  else if(q.length===64) location='/block/hash/'+q;
}

function ram(r){
  const cls=(r||'DDR4').toLowerCase();
  return `<span class="ram ${cls}">${r||'DDR4'}</span>`;
}

function age(ts){
  const d=Math.floor(Date.now()/1000)-ts;
  if(d<60) return d+'s';if(d<3600) return Math.floor(d/60)+'m';
  if(d<86400) return Math.floor(d/3600)+'h';return Math.floor(d/86400)+'d';
}

function fn(n){return Number(n).toLocaleString('en');}

async function load(){
  document.getElementById('ts').textContent=new Date().toLocaleTimeString();
  await Promise.all([loadSummary(),loadMiners(),loadBlocks()]);
}

async function loadSummary(){
  const d=await fetch('/api/summary').then(r=>r.json()).catch(()=>null);
  if(!d||d.error) return;
  document.getElementById('net-pill').textContent=d.network||'mainnet';
  const ep=d.epoch||0;
  const epPct=((d.height||0)%100000/1000).toFixed(2);
  const cards=[
    {l:'Height',    v:fn(d.height),         s:'blocks mined',                ac:'--cyan'},
    {l:'Difficulty',v:d.difficulty,          s:('0'.repeat(d.difficulty||0)+'…').slice(0,10)+' target', ac:'--amber'},
    {l:'Next Reward',v:(d.next_reward||0).toFixed(2), s:'POLM per block',    ac:'--green'},
    {l:'Epoch',     v:ep,                    s:epPct+'% complete',            ac:'--purple'},
    {l:'Block Time', v:(d.block_time||120)+'s', s:'120s target',             ac:'--cyan'},
    {l:'Chain Tip', v:(d.tip_hash||'').slice(0,8)+'…', s:'sha3-256',        ac:'--cyan'},
    {l:'Mempool',   v:d.mempool_size||0,     s:'pending txs',                ac:'--amber'},
    {l:'Peers',     v:d.peers||0,            s:'connected nodes',            ac:'--green'},
  ];
  document.getElementById('sg').innerHTML=cards.map(c=>
    `<div class="sc" style="--ac:var(${c.ac})"><div class="sc-l">${c.l}</div><div class="sc-v">${c.v}</div><div class="sc-s">${c.s}</div></div>`
  ).join('');
  const sup=d.total_supply||0, max=210000000, pct=(sup/max*100).toFixed(4);
  document.getElementById('sm').textContent=fn(Math.round(sup))+' POLM mined';
  document.getElementById('sb').style.width=Math.min(pct,100)+'%';
  document.getElementById('spct2').textContent=pct+'% of max supply';
  document.getElementById('ni').innerHTML=[
    ['Symbol','POLM'],
    ['Max supply','210,000,000'],
    ['Block time','120 seconds (2 min)'],
    ['Halving','every epoch (100,000 blocks, ~138 days)'],
    ['Score','1 / latency_ns'],
    ['Retarget','every 144 blocks (±25%)'],
    ['Hash algo','SHA3-256'],
    ['Version',d.version||'2.0.0'],
  ].map(([k,v])=>`<div class="irow"><span class="ik">${k}</span><span class="iv">${v}</span></div>`).join('');
}

async function loadMiners(){
  const d=await fetch('/api/miners').then(r=>r.json()).catch(()=>({}));
  const miners=Object.entries(d).sort((a,b)=>b[1].blocks-a[1].blocks);
  const total=miners.reduce((s,[,v])=>s+v.blocks,0);
  document.getElementById('lb-count').textContent=miners.length?`(${miners.length} miners)`:'';
  document.getElementById('lb').innerHTML=miners.slice(0,8).map(([id,v],i)=>{
    const pct=total?(v.blocks/total*100):0, col=RC[v.ram]||'#00e5ff';
    return`<div class="lrow">
      <div class="rnk ${i<3?'r'+(i+1):''}">${i<3?['①','②','③'][i]:'#'+(i+1)}</div>
      <div class="minfo">
        <div class="maddr">${id.slice(0,24)}…</div>
        <div class="mmeta">${ram(v.ram)}<span style="color:var(--t3)">${(v.avg_latency||0).toFixed(0)}ns avg</span><span style="color:${col}">${(v.reward||0).toFixed(0)} POLM earned</span></div>
        ${v.cpu ? `<div style="font-family:var(--mono);font-size:.68rem;color:var(--t3);margin-top:2px">⚙ ${v.cpu}</div>` : ''}
      ${v.os ? `<div style="font-family:var(--mono);font-size:.68rem;color:var(--t3);margin-top:1px">🖥 ${v.os}</div>` : ''}
      </div>
      <div><div class="bar-wrap"><div class="bar-fill" style="width:${Math.min(pct,100).toFixed(1)}%;background:${col}"></div></div><div class="num mc" style="font-size:.6rem;margin-top:1px">${pct.toFixed(1)}%</div></div>
      <div class="num cc">${v.blocks}</div>
      <div class="num gc">${(v.reward||0).toFixed(0)}</div>
      <div class="num ac">${(v.avg_latency||0).toFixed(0)}ns</div>
    </div>`;
  }).join('')||'<div style="color:var(--t3);font-family:var(--mono);font-size:.75rem;padding:12px 0">No miners yet.</div>';
}

async function loadBlocks(){
  const blocks=await fetch('/api/blocks?limit=30').then(r=>r.json()).catch(()=>[]);
  document.getElementById('blk-count').textContent=blocks.length?`showing ${blocks.length}`:'';
  renderBlocks('bt',blocks);
}

function renderBlocks(id,blocks){
  const tb=document.getElementById(id);
  if(!blocks.length){tb.innerHTML='<tr><td colspan="9" style="color:var(--t3);text-align:center;padding:20px">No blocks yet.</td></tr>';return;}
  tb.innerHTML=blocks.map(item=>{
    const b=item.block||item, col=RC[b.ram_type]||'#00e5ff';
    return`<tr onclick="location='/block/${b.height}'">
      <td><a class="hl" href="/block/${b.height}">${fn(b.height)}</a></td>
      <td style="color:var(--t3)">${(b.block_hash||'').slice(0,12)}…</td>
      <td style="color:${col}">${(b.miner_id||'').slice(0,18)}…</td>
      <td>${ram(b.ram_type||'DDR4')}</td>
      <td style="color:var(--amber)">${(b.latency_ns||0).toFixed(0)}ns</td>
      <td style="color:var(--t3)">${fn(Math.round(b.score||0))}</td>
      <td style="color:var(--t3)">${fn(b.nonce||0)}</td>
      <td style="color:var(--green)">${(b.reward||0).toFixed(2)}</td>
      <td style="color:var(--t3)">${age(b.timestamp||0)}</td>
    </tr>`;
  }).join('');
  // pega genesis hash do bloco #0
  const genesis=blocks.find(item=>(item.block||item).height===0);
  if(genesis){
    const gh=document.getElementById('genesis-hash');
    if(gh) gh.textContent=(genesis.block||genesis).block_hash||'—';
  }
}

async function loadRanking(){
  const d=await fetch('/api/miners').then(r=>r.json()).catch(()=>({}));
  const miners=Object.entries(d).sort((a,b)=>b[1].blocks-a[1].blocks);
  const total=miners.reduce((s,[,v])=>s+v.blocks,0);
  const top=miners.slice(0,3);
  const podOrder=top.length>=3?[top[1],top[0],top[2]]:top;
  document.getElementById('podium').innerHTML=podOrder.map((item,pi)=>{
    if(!item) return '<div></div>';
    const [id,v]=item, ri=top.indexOf(item), col=RC[v.ram]||'#00e5ff', pct=total?(v.blocks/total*100):0;
    return`<div class="pod p${ri+1}" style="order:${pi===0?2:pi===1?1:3}">
      <div class="pod-rank">${MEDALS[ri]||'🏅'}</div>
      <div class="pod-addr">${id.slice(0,28)}…</div>
      <div class="pod-ram">${ram(v.ram)} <span style="color:${col};font-family:var(--mono);font-size:.7rem">${(v.avg_latency||0).toFixed(0)}ns avg</span></div>
      <div class="pod-blocks" style="color:${col}">${fn(v.blocks)}</div>
      <div class="pod-pct">${pct.toFixed(1)}% of blocks</div>
      <div class="pod-polm">${(v.reward||0).toFixed(0)} POLM</div>
    </div>`;
  }).join('');
  document.getElementById('full-rank').innerHTML=miners.map(([id,v],i)=>{
    const pct=total?(v.blocks/total*100):0, col=RC[v.ram]||'#00e5ff';
    return`<div class="rrow">
      <div class="rnk ${i<3?'r'+(i+1):''}" style="color:${RK[i]||'var(--t3)'}">#${i+1}</div>
      <div class="minfo"><div class="maddr">${id.slice(0,26)}…</div><div class="mmeta">${ram(v.ram)}</div></div>
      <div><div class="bar-wrap"><div class="bar-fill" style="width:${Math.min(pct,100).toFixed(1)}%;background:${col}"></div></div><div class="num mc" style="font-size:.58rem;margin-top:1px">${pct.toFixed(1)}%</div></div>
      <div class="num cc">${fn(v.blocks)}</div>
      <div class="num gc">${(v.reward||0).toFixed(0)}</div>
      <div class="num ac">${(v.avg_latency||0).toFixed(0)}ns</div>
      <div class="num">${ram(v.ram)}</div>
    </div>`;
  }).join('')||'<div style="color:var(--t3);font-family:var(--mono);font-size:.75rem;padding:20px;text-align:center">No miners yet.</div>';
}

async function loadAllBlocks(){
  blkOffset=0;
  const blocks=await fetch('/api/blocks?limit=50&offset=0').then(r=>r.json()).catch(()=>[]);
  document.getElementById('all-blk-count').textContent=`showing ${blocks.length}`;
  renderBlocks('all-bt',blocks);
}

async function loadMore(){
  blkOffset+=50;
  const blocks=await fetch(`/api/blocks?limit=50&offset=${blkOffset}`).then(r=>r.json()).catch(()=>[]);
  const tb=document.getElementById('all-bt');
  blocks.forEach(item=>{
    const b=item.block||item, col=RC[b.ram_type]||'#00e5ff';
    const tr=document.createElement('tr');
    tr.onclick=()=>location='/block/'+b.height;
    tr.innerHTML=`<td><a class="hl" href="/block/${b.height}">${fn(b.height)}</a></td><td style="color:var(--t3)">${(b.block_hash||'').slice(0,12)}…</td><td style="color:${col}">${(b.miner_id||'').slice(0,18)}…</td><td>${ram(b.ram_type||'DDR4')}</td><td style="color:var(--amber)">${(b.latency_ns||0).toFixed(0)}ns</td><td style="color:var(--t3)">${fn(Math.round(b.score||0))}</td><td style="color:var(--t3)">${fn(b.nonce||0)}</td><td style="color:var(--green)">${(b.reward||0).toFixed(2)}</td><td style="color:var(--t3)">${age(b.timestamp||0)}</td>`;
    tb.appendChild(tr);
  });
}

async function loadProto(){
  const d=await fetch('/api/summary').then(r=>r.json()).catch(()=>null);
  if(!d) return;
  document.getElementById('proto-net').innerHTML=[
    ['Symbol','POLM'],
    ['Network',d.network||'mainnet'],
    ['Version',d.version||'2.0.0'],
    ['Height',fn(d.height||0)],
    ['Difficulty',d.difficulty||4],
    ['Epoch',d.epoch||0],
    ['DAG size',(d.dag_size_mb||256)+'MB'],
    ['Max supply','210,000,000 POLM'],
    ['Block time','120 seconds (2 min)'],
    ['Score formula','1 / latency_ns'],
    ['Halving interval','100,000 blocks per epoch (~138 days)'],
    ['Retarget window','144 blocks (±25%)'],
    ['Max threads','4 per miner'],
    ['Founder lock','5,256,000 blocks (~5yr)'],
    ['Founder alloc','10,500,000 POLM (5%) locked'],
    ['Polygon ERC-20','0x79175931C54c9765E5846229a0eB118ef24fdE55'],
    ['DEX','QuickSwap (coming soon)'],
  ].map(([k,v])=>`<div class="irow"><span class="ik">${k}</span><span class="iv">${v}</span></div>`).join('');
}

load();
setInterval(load,8000);
</script>
</body>
</html>"""


def create_explorer(node_url: str = "http://localhost:6060", port: int = 5050):
    app = Flask("polm-explorer")

    def fetch(path: str):
        try:
            r = urllib.request.urlopen(f"{node_url}{path}", timeout=5)
            return json.loads(r.read())
        except Exception:
            return None

    @app.route("/")
    def index():
        return Response(HTML, mimetype="text/html")

    @app.route("/api/summary")
    def api_summary():
        d = fetch("/")
        return app.response_class(json.dumps(d or {"error":"offline"}), mimetype="application/json")

    @app.route("/api/blocks")
    def api_blocks():
        limit  = min(int(request.args.get("limit", 50)), 200)
        offset = int(request.args.get("offset", 0))
        d = fetch(f"/chain?limit={limit}&offset={offset}")
        return app.response_class(json.dumps(d or []), mimetype="application/json")

    @app.route("/api/miners")
    def api_miners():
        d = fetch("/miners")
        return app.response_class(json.dumps(d or {}), mimetype="application/json")

    @app.route("/block/<int:h>")
    def block_detail(h: int):
        item = fetch(f"/block/{h}")
        if not item:
            return "Block not found", 404
        b   = item.get("block", item)
        ts  = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(b.get("timestamp", 0)))
        txs = item.get("txs", [])
        rows = [
            ("height",        str(b.get("height","")),                      "cyan"),
            ("block hash",    b.get("block_hash",""),                        "cyan"),
            ("prev hash",     b.get("prev_hash",""),                         ""),
            ("timestamp",     f"{b.get('timestamp','')} — {ts}",           ""),
            ("miner",         b.get("miner_id",""),                          "amber"),
            ("RAM type",      b.get("ram_type",""),                          ""),
            ("score formula", "1 / latency_ns  (no boost, no penalty)",     ""),
            ("threads",       str(b.get("threads","")),                      ""),
            ("epoch",         str(b.get("epoch","")),                        ""),
            ("difficulty",    str(b.get("difficulty","")),                   ""),
            ("nonce",         f"{b.get('nonce',0):,}",                     ""),
            ("latency proof", f"{b.get('latency_ns',0):.2f} ns",           "amber"),
            ("memory proof",  b.get("mem_proof",""),                         ""),
            ("score",         f"{b.get('score',0):,.6f}",                  ""),
            ("reward",        f"{b.get('reward',0)} POLM",                 "green"),
            ("transactions",  str(len(txs)),                                 "cyan"),
        ]
        return render_template_string(BLOCK_HTML, height=h, rows=rows,
            website=WEBSITE, twitter=TWITTER_P, version=VERSION)

    @app.route("/block/hash/<h>")
    def block_by_hash(h: str):
        blocks = fetch("/chain?limit=500") or []
        for item in blocks:
            b = item.get("block", item)
            if b.get("block_hash") == h:
                return block_detail(b["height"])
        return "Block not found", 404

    print(f"\n  PoLM Explorer  v{VERSION}")
    print(f"  {WEBSITE}")
    print(f"  http://localhost:{port}")
    print(f"  Node: {node_url}")
    print(f"  Score: 1/latency_ns — any RAM mines\n")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    import sys
    node = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:6060"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5050
    create_explorer(node_url=node, port=port)
