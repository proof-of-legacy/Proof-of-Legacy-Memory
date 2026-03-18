"""
PoLM Explorer  v2.0.0  —  Professional Edition
https://polm.com.br

Dashboard · Ranking · Blocks · Protocol
Founder : @aluisiofer  |  Project : @polm2026
"""

from flask import Flask, render_template_string, jsonify, request, Response
import json, time, urllib.request

VERSION   = "2.1.0"
WEBSITE   = "https://polm.com.br"
GITHUB    = "https://github.com/proof-of-legacy/Proof-of-Legacy-Memory"
TWITTER_P = "https://x.com/polm2026"
TWITTER_F = "https://x.com/aluisiofer"
GENESIS   = "87df8a87c7befd2cde053569ed89c03f6502b33f4a910bb47284e66277a77fa5"

BLOCK_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Block #{{ height }} — PoLM Explorer</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#07080a;--s1:#0d1017;--b1:#1e2a38;--cyan:#22d3ee;--green:#22c55e;--amber:#f59e0b;--t1:#f0f4f8;--t2:#8ba3bc;--t3:#3d5166;--mono:'JetBrains Mono',monospace;--sans:'Space Grotesk',sans-serif}
body{background:var(--bg);color:var(--t1);font-family:var(--sans);padding:24px 18px}
nav{background:rgba(13,16,23,.98);border-bottom:1px solid var(--b1);height:54px;display:flex;align-items:center;padding:0 24px;gap:14px;position:fixed;top:0;left:0;right:0;z-index:99;backdrop-filter:blur(16px)}
.logo{font-family:var(--mono);font-weight:700;color:var(--cyan);font-size:.95rem;text-decoration:none}
.back{font-family:var(--mono);font-size:.72rem;color:var(--t2);text-decoration:none;border:1px solid var(--b1);padding:5px 12px;border-radius:6px;margin-left:auto}
.back:hover{color:var(--cyan);border-color:var(--cyan)}
.wrap{max-width:900px;margin:70px auto 0}
h1{font-family:var(--mono);font-size:1.2rem;color:var(--cyan);margin-bottom:18px}
.card{background:var(--s1);border:1px solid var(--b1);border-radius:12px;overflow:hidden}
.row{display:grid;grid-template-columns:160px 1fr;border-bottom:1px solid rgba(30,42,56,.5);padding:12px 18px}
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
<meta name="description" content="PoLM Blockchain Explorer — Proof of Legacy Memory. Live stats, mining leaderboard, block explorer.">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#07080a;--s1:#0d1017;--s2:#121820;--s3:#181f2a;--b1:#1e2a38;--b2:#263346;
  --cyan:#22d3ee;--cyan2:#0891b2;--green:#22c55e;--amber:#f59e0b;--orange:#f97316;
  --purple:#a78bfa;--red:#ef4444;
  --t1:#f0f4f8;--t2:#8ba3bc;--t3:#3d5166;
  --mono:'JetBrains Mono',monospace;--sans:'Space Grotesk',sans-serif;--r:8px;--r2:12px}
html{font-size:13px;scroll-behavior:smooth}
body{background:var(--bg);color:var(--t1);font-family:var(--sans);
  background-image:radial-gradient(ellipse 80% 50% at 50% -5%,rgba(34,211,238,.05) 0%,transparent 65%)}
nav{background:rgba(13,16,23,.98);border-bottom:1px solid var(--b1);height:54px;display:flex;align-items:center;padding:0 24px;gap:14px;position:sticky;top:0;z-index:999;backdrop-filter:blur(16px)}
.logo{font-family:var(--mono);font-weight:700;font-size:.95rem;color:var(--cyan);letter-spacing:.04em;white-space:nowrap;text-decoration:none}
.logo em{color:var(--t3);font-style:normal;font-weight:300}
.site{font-size:.6rem;color:var(--t3);font-family:var(--mono);border-left:1px solid var(--b1);padding-left:12px;white-space:nowrap}
.pill{padding:3px 10px;border-radius:20px;font-size:.6rem;font-family:var(--mono);font-weight:500}
.pill-net{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);color:#22c55e;display:flex;align-items:center;gap:5px}
.pill-net::before{content:'';width:5px;height:5px;border-radius:50%;background:#22c55e;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.nav-tabs{display:flex;gap:2px;margin-left:8px}
.tab{padding:5px 13px;border-radius:6px;font-size:.7rem;cursor:pointer;color:var(--t2);border:1px solid transparent;transition:all .15s;font-family:var(--mono)}
.tab:hover{color:var(--t1);background:var(--s2)}
.tab.active{color:var(--cyan);background:rgba(34,211,238,.08);border-color:rgba(34,211,238,.15)}
.nav-right{margin-left:auto;display:flex;align-items:center;gap:8px}
#ts{font-size:.6rem;color:var(--t3);font-family:var(--mono)}
.rbtn{background:transparent;border:1px solid var(--b1);color:var(--t2);padding:5px 12px;border-radius:6px;cursor:pointer;font-family:var(--mono);font-size:.65rem;transition:all .15s}
.rbtn:hover{border-color:var(--cyan);color:var(--cyan)}
.page{display:none;max-width:1480px;margin:0 auto;padding:20px 18px}
.page.active{display:block}
.sbar{display:flex;gap:8px;margin-bottom:20px;max-width:580px}
.sbar input{flex:1;background:var(--s1);border:1px solid var(--b1);border-radius:var(--r);padding:9px 14px;color:var(--t1);font-family:var(--mono);font-size:.8rem;outline:none;transition:border-color .15s}
.sbar input:focus{border-color:var(--cyan)}
.sbar input::placeholder{color:var(--t3)}
.sbar button{background:var(--cyan);border:none;color:#000;padding:9px 18px;border-radius:var(--r);cursor:pointer;font-family:var(--sans);font-size:.75rem;font-weight:600;transition:background .15s}
.sbar button:hover{background:var(--cyan2);color:#fff}
.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(148px,1fr));gap:8px;margin-bottom:18px}
.sc{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:14px;position:relative;overflow:hidden;transition:border-color .15s}
.sc::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--ac,var(--cyan));opacity:.5}
.sc:hover{border-color:var(--b2)}
.sc-l{font-size:.58rem;color:var(--t3);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px;font-family:var(--mono)}
.sc-v{font-size:1.2rem;font-weight:700;color:var(--t1);font-family:var(--mono);line-height:1.1}
.sc-s{font-size:.6rem;color:var(--t3);margin-top:3px;font-family:var(--mono)}
.sec{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:18px;margin-bottom:14px}
.st{font-size:.6rem;font-weight:600;letter-spacing:.15em;text-transform:uppercase;color:var(--t2);margin-bottom:14px;display:flex;align-items:center;gap:8px;font-family:var(--mono)}
.st::after{content:'';flex:1;height:1px;background:var(--b1)}
.st span{color:var(--t3);font-size:.58rem;font-weight:400;letter-spacing:0;text-transform:none;margin-left:4px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
@media(max-width:900px){.two{grid-template-columns:1fr}}
.sup-wrap{margin-top:8px}
.sup-row{display:flex;justify-content:space-between;font-size:.75rem;font-family:var(--mono);margin-bottom:5px}
.sup-bar{height:6px;background:var(--s3);border-radius:3px;overflow:hidden;margin:4px 0 8px}
.sup-fill{height:100%;background:linear-gradient(90deg,var(--cyan2),var(--cyan));border-radius:3px;transition:width 1s}
.sup-meta{display:flex;justify-content:space-between;font-size:.6rem;color:var(--t3);font-family:var(--mono)}
.lb-hdr{display:grid;grid-template-columns:28px 1fr 90px 60px 70px 52px 44px;gap:8px;padding:0 0 8px;border-bottom:1px solid var(--b1);margin-bottom:4px}
.lb-hdr span{font-size:.58rem;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;font-family:var(--mono)}
.lb-hdr span:not(:nth-child(2)){text-align:right}
.lb-hdr span:nth-child(2){text-align:left}
.lrow{display:grid;grid-template-columns:28px 1fr 90px 60px 70px 52px 44px;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid rgba(30,42,56,.5);transition:background .1s}
.lrow:last-child{border-bottom:none}
.lrow:hover{background:rgba(34,211,238,.02)}
.rnk{font-family:var(--mono);font-size:.72rem;font-weight:700;color:var(--t3);text-align:center}
.rnk.r1{color:#fbbf24}.rnk.r2{color:#9ca3af}.rnk.r3{color:#cd7f32}
.minfo{min-width:0}
.maddr{font-family:var(--mono);font-size:.72rem;color:var(--cyan);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
.maddr:hover{text-decoration:underline}
.mmeta{font-size:.6rem;color:var(--t3);margin-top:2px;font-family:var(--mono);display:flex;align-items:center;gap:6px}
.bar-wrap{position:relative;height:4px;background:var(--s3);border-radius:2px;overflow:hidden}
.bar-fill{height:100%;border-radius:2px;transition:width .6s}
.num{font-family:var(--mono);font-size:.72rem;text-align:right;white-space:nowrap}
.gc{color:var(--green)}.ac{color:var(--amber)}.cc{color:var(--cyan)}.mc{color:var(--t3)}.rc{color:var(--red)}
.ram{display:inline-block;padding:2px 7px;border-radius:4px;font-size:.6rem;font-weight:700;font-family:var(--mono)}
.ddr2{background:rgba(249,115,22,.1);color:#fb923c;border:1px solid rgba(249,115,22,.2)}
.ddr3{background:rgba(245,158,11,.08);color:#fbbf24;border:1px solid rgba(245,158,11,.18)}
.ddr4{background:rgba(34,211,238,.07);color:var(--cyan);border:1px solid rgba(34,211,238,.14)}
.ddr5{background:rgba(239,68,68,.08);color:#f87171;border:1px solid rgba(239,68,68,.15)}
.bgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
@media(max-width:600px){.bgrid{grid-template-columns:repeat(2,1fr)}}
.bc{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);padding:14px;text-align:center;transition:border-color .15s}
.bc:hover{border-color:var(--b2)}
.bt{font-family:var(--mono);font-size:.95rem;font-weight:700;margin-bottom:3px}
.bm{font-size:1.5rem;font-weight:700;font-family:var(--mono);margin-bottom:2px}
.bs{font-size:.58rem;color:var(--t3);font-family:var(--mono)}
.bpen{font-size:.58rem;margin-top:3px;font-family:var(--mono)}
.b2 .bt,.b2 .bm{color:#fb923c}.b3 .bt,.b3 .bm{color:#fbbf24}
.b4 .bt,.b4 .bm{color:var(--cyan)}.b5 .bt,.b5 .bm{color:#f87171}
table{width:100%;border-collapse:collapse;font-size:.72rem}
th{text-align:left;padding:7px 10px;color:var(--t3);font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;border-bottom:1px solid var(--b1);font-family:var(--mono);font-weight:400;white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid rgba(30,42,56,.4);vertical-align:middle;font-family:var(--mono)}
tbody tr{cursor:pointer;transition:background .1s}
tbody tr:hover td{background:rgba(34,211,238,.025)}
tbody tr:last-child td{border-bottom:none}
a.hl{color:var(--cyan);text-decoration:none}
a.hl:hover{text-decoration:underline}
.irow{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid rgba(30,42,56,.4);font-size:.75rem}
.irow:last-child{border-bottom:none}
.ik{color:var(--t3);font-family:var(--mono)}.iv{color:var(--t1);font-family:var(--mono);font-weight:500}
.rank-hero{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:24px;margin-bottom:14px;text-align:center}
.rank-hero h2{font-size:1.2rem;font-weight:700;margin-bottom:6px;font-family:var(--mono);color:var(--cyan)}
.rank-hero p{font-size:.75rem;color:var(--t2);font-family:var(--mono)}
.podium{display:grid;grid-template-columns:1fr 1.1fr 1fr;gap:12px;margin:20px 0;align-items:end}
@media(max-width:600px){.podium{grid-template-columns:1fr}}
.pod{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r2);padding:16px;text-align:center;transition:all .2s}
.pod:hover{transform:translateY(-2px)}
.pod.p1{border-color:rgba(251,191,36,.3);background:rgba(251,191,36,.04)}
.pod.p2{border-color:rgba(156,163,175,.2)}
.pod.p3{border-color:rgba(205,127,50,.2)}
.pod-rank{font-size:1.8rem;margin-bottom:8px}
.pod-addr{font-family:var(--mono);font-size:.68rem;color:var(--cyan);margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pod-blocks{font-family:var(--mono);font-size:1.6rem;font-weight:700;color:var(--t1)}
.pod-pct{font-size:.7rem;color:var(--t3);font-family:var(--mono)}
.pod-polm{font-size:.8rem;color:var(--green);font-family:var(--mono);margin-top:4px}
.pod-ram{margin-top:6px}
.rank-hdr{display:grid;grid-template-columns:28px 1fr 80px 70px 70px 65px 55px 50px;gap:8px;padding:6px 0 8px;border-bottom:1px solid var(--b1);margin-bottom:4px}
.rank-hdr span{font-size:.57rem;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;font-family:var(--mono)}
.rank-hdr span:not(:nth-child(2)){text-align:right}
.rank-hdr span:nth-child(2){text-align:left}
.rrow{display:grid;grid-template-columns:28px 1fr 80px 70px 70px 65px 55px 50px;align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid rgba(30,42,56,.4);transition:background .1s}
.rrow:last-child{border-bottom:none}
.rrow:hover{background:rgba(34,211,238,.02)}
.pen-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}
@media(max-width:600px){.pen-grid{grid-template-columns:repeat(3,1fr)}}
.pen-card{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);padding:12px;text-align:center}
.pen-t{font-size:.65rem;color:var(--t2);font-family:var(--mono);margin-bottom:4px}
.pen-v{font-size:1rem;font-weight:700;font-family:var(--mono);color:var(--amber)}
.genesis-card{background:var(--s2);border:1px solid rgba(34,211,238,.15);border-radius:var(--r2);padding:16px;margin-bottom:14px}
.genesis-label{font-size:.6rem;color:var(--t3);font-family:var(--mono);text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px}
.genesis-hash{font-family:var(--mono);font-size:.75rem;color:var(--cyan);word-break:break-all;line-height:1.5}
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

<!-- DASHBOARD -->
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
      <div class="sup-row"><span id="sm" style="color:var(--cyan)"></span><span style="color:var(--t3)">/ 32,000,000 POLM max</span></div>
      <div class="sup-bar"><div class="sup-fill" id="sb" style="width:0%"></div></div>
      <div class="sup-meta"><span id="spct2"></span><span>halving ~4yr · 5.0 POLM initial reward</span></div>
    </div>
  </div>
  <div class="two">
    <div class="sec">
      <div class="st">Live leaderboard <span id="lb-count"></span></div>
      <div class="lb-hdr"><span>#</span><span>Miner</span><span>Share</span><span>Blocks</span><span>POLM</span><span>Lat</span><span>Boost</span></div>
      <div id="lb"></div>
    </div>
    <div>
      <div class="sec" style="margin-bottom:14px">
        <div class="st">Network</div>
        <div id="ni"></div>
      </div>
      <div class="sec">
        <div class="st">Legacy boost</div>
        <div class="bgrid">
          <div class="bc b2"><div class="bt">DDR2</div><div class="bm">12×</div><div class="bs">~3500–8000 ns</div><div class="bpen" style="color:var(--green)">max legacy now</div></div>
          <div class="bc b3"><div class="bt">DDR3</div><div class="bm">10×</div><div class="bs">~1500–4000 ns</div><div class="bpen" style="color:var(--amber)">strong legacy</div></div>
          <div class="bc b4"><div class="bt">DDR4</div><div class="bm">1×</div><div class="bs">~900–1900 ns</div><div class="bpen" style="color:var(--cyan)">baseline now</div></div>
          <div class="bc b5"><div class="bt">DDR5</div><div class="bm">0.5×</div><div class="bs">~500–900 ns</div><div class="bpen" style="color:var(--red)">penalized now</div></div>
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

<!-- RANKING -->
<div class="page" id="page-ranking">
<div style="max-width:1480px;margin:0 auto;padding:20px 18px">
  <div class="rank-hero">
    <h2>⛏ Mining Leaderboard</h2>
    <p>Ranked by blocks mined · Updated every 8s · Legacy hardware rewarded</p>
  </div>
  <div class="podium" id="podium"></div>
  <div class="sec">
    <div class="st">Full rankings</div>
    <div class="rank-hdr"><span>#</span><span>Miner</span><span>Share</span><span>Blocks</span><span>POLM</span><span>Latency</span><span>Boost</span><span>RAM</span></div>
    <div id="full-rank"></div>
  </div>
  <div class="sec">
    <div class="st">Thread saturation penalty</div>
    <div class="pen-grid">
      <div class="pen-card"><div class="pen-t">1–2 threads</div><div class="pen-v">1.00×</div></div>
      <div class="pen-card"><div class="pen-t">3–4 threads</div><div class="pen-v">0.90×</div></div>
      <div class="pen-card"><div class="pen-t">5–8 threads</div><div class="pen-v">0.80×</div></div>
      <div class="pen-card"><div class="pen-t">9–16 threads</div><div class="pen-v">0.65×</div></div>
      <div class="pen-card"><div class="pen-t">17+ threads</div><div class="pen-v">0.50×</div></div>
    </div>
  </div>
</div>
</div>

<!-- BLOCKS -->
<div class="page" id="page-blocks">
<div style="max-width:1480px;margin:0 auto;padding:20px 18px">
  <div class="genesis-card">
    <div class="genesis-label">Genesis block — block #0</div>
    <div class="genesis-hash">87df8a87c7befd2cde053569ed89c03f6502b33f4a910bb47284e66277a77fa5</div>
    <div style="font-size:.62rem;color:var(--t3);font-family:var(--mono);margin-top:6px">"Legacy hardware deserves a second life — PoLM Genesis, March 2026, polm.com.br"</div>
  </div>
  <div class="sec">
    <div class="st">All blocks <span id="all-blk-count"></span></div>
    <table><thead><tr><th>Height</th><th>Hash</th><th>Miner</th><th>RAM</th><th>Latency</th><th>Score</th><th>Nonce</th><th>Reward</th><th>Age</th></tr></thead>
    <tbody id="all-bt"></tbody></table>
    <div style="text-align:center;margin-top:14px"><button class="rbtn" onclick="loadMore()">Load more</button></div>
  </div>
</div>
</div>

<!-- PROTOCOL -->
<div class="page" id="page-protocol">
<div style="max-width:1480px;margin:0 auto;padding:20px 18px">
  <div class="two">
    <div class="sec"><div class="st">Protocol parameters</div><div id="proto-net"></div></div>
    <div class="sec">
      <div class="st">Algorithm</div>
      <div class="irow"><span class="ik">Score formula</span><span class="iv" style="color:var(--cyan)">(1/latency) × boost × penalty</span></div>
      <div class="irow"><span class="ik">Dynamic boost</span><span class="iv">(latency/1000)^0.8</span></div>
      <div class="irow"><span class="ik">Baseline</span><span class="iv">1000 ns (DDR4)</span></div>
      <div class="irow"><span class="ik">DAG mainnet</span><span class="iv">256 MB + 64 MB/epoch</span></div>
      <div class="irow"><span class="ik">Walk steps</span><span class="iv">100,000 per nonce</span></div>
      <div class="irow"><span class="ik">Hash function</span><span class="iv">SHA3-256</span></div>
      <div class="irow"><span class="ik">Signatures</span><span class="iv">ECDSA secp256k1</span></div>
      <div class="irow"><span class="ik">Coin type</span><span class="iv">SLIP-44 #637</span></div>
    </div>
  </div>
  <div class="sec">
    <div class="st">Boost table — validated testnet (816 blocks)</div>
    <div class="bgrid">
      <div class="bc b2"><div class="bt">DDR2</div><div class="bm">12×</div><div class="bs">Halving 1 — max</div><div class="bpen" style="color:var(--green)">Core2Duo 2006 ✓</div></div>
      <div class="bc b3"><div class="bt">DDR3</div><div class="bm">10×</div><div class="bs">Halving 1 — strong</div><div class="bpen" style="color:var(--amber)">Legacy bonus ✓</div></div>
      <div class="bc b4"><div class="bt">DDR4</div><div class="bm">1×→8×</div><div class="bs">Grows each halving</div><div class="bpen" style="color:var(--cyan)">Dominates yr 6 ✓</div></div>
      <div class="bc b5"><div class="bt">DDR5</div><div class="bm">0.5×→10×</div><div class="bs">Grows each halving</div><div class="bpen" style="color:var(--purple)">Dominates yr 10 ✓</div></div>
    </div>
  </div>
  <div class="sec">
    <div class="st">Halving schedule</div>
    <table><thead><tr><th>Period</th><th>Height range</th><th>Reward</th><th>Year</th><th>RAM / DAG</th></tr></thead>
    <tbody>
      <tr><td style="color:var(--cyan)">1</td><td>0 – 2,099,999</td><td style="color:var(--green)">5.0 POLM</td><td>Year 0–2</td><td>DAG 256MB · DDR2=12× · min 4GB</td></tr>
      <tr><td>2</td><td>2.1M – 4.2M</td><td>2.5 POLM</td><td>Year 2–4</td><td>DAG 512MB · DDR4=4× · min 8GB</td></tr>
      <tr><td>3</td><td>4.2M – 6.3M</td><td>1.25 POLM</td><td>Year 4–6</td><td>DAG 1GB · DDR4=6× · min 16GB</td></tr>
      <tr><td>4</td><td>6.3M – 8.4M</td><td>0.625 POLM</td><td>Year 6–8</td><td>DAG 2GB · DDR5=6× · min 32GB</td></tr>
      <tr><td>5</td><td>8.4M – 10.5M</td><td>0.3125 POLM</td><td>Year 8–10</td><td>DAG 4GB · DDR5=8× · min 64GB</td></tr>
      <tr><td>6</td><td>10.5M – 12.6M</td><td>0.156 POLM</td><td>Year 10–12</td><td>DAG 8GB · DDR5=10× · min 128GB</td></tr>
      <tr><td style="color:var(--amber)">7</td><td>12.6M – 14.7M</td><td>0.078 POLM</td><td>Year 12–14</td><td style="color:var(--amber)">DAG 16GB · DDR6=12× · min 256GB ← RAM board!</td></tr>
      <tr><td style="color:var(--red)">8+</td><td>14.7M+</td><td>decreasing</td><td>Year 14+</td><td style="color:var(--red)">DAG 32GB+ · DDR7=12× · min 512GB ← new market</td></tr>
    </tbody></table>
  </div>
  <div class="sec">
    <div class="st">Links</div>
    <div class="irow"><span class="ik">Website</span><a class="iv hl" href="https://polm.com.br" target="_blank">polm.com.br</a></div>
    <div class="irow"><span class="ik">GitHub</span><a class="iv hl" href="https://github.com/proof-of-legacy/Proof-of-Legacy-Memory" target="_blank">proof-of-legacy/Proof-of-Legacy-Memory</a></div>
    <div class="irow"><span class="ik">Project Twitter</span><a class="iv hl" href="https://x.com/polm2026" target="_blank">@polm2026</a></div>
    <div class="irow"><span class="ik">Founder</span><a class="iv hl" href="https://x.com/aluisiofer" target="_blank">@aluisiofer (Aluísio Fernandes — Aluminium)</a></div>
    <div class="irow"><span class="ik">Node API</span><a class="iv hl" href="http://node1.polm.com.br:6060/" target="_blank">node1.polm.com.br:6060</a></div>
  </div>
</div>
</div>

<footer>
  <div class="fl">PoLM Explorer v2.0.0 &nbsp;·&nbsp; <a href="https://polm.com.br">polm.com.br</a> &nbsp;·&nbsp; MIT License &nbsp;·&nbsp; Mainnet</div>
  <div class="fl"><a href="https://x.com/polm2026" target="_blank">@polm2026</a> &nbsp;·&nbsp; <a href="https://x.com/aluisiofer" target="_blank">@aluisiofer</a> &nbsp;·&nbsp; <a href="https://github.com/proof-of-legacy/Proof-of-Legacy-Memory" target="_blank">GitHub</a></div>
</footer>

<script>
const RC={DDR2:'#fb923c',DDR3:'#fbbf24',DDR4:'#22d3ee',DDR5:'#f87171'};
const BOOST={DDR2:10,DDR3:8,DDR4:1,DDR5:0.5};
const MEDALS=['🥇','🥈','🥉'];
const RK=['#fbbf24','#9ca3af','#cd7f32'];
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

function ram(r){return `<span class="ram ${r.toLowerCase()}">${r}</span>`;}

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
  const cards=[
    {l:'Height',v:fn(d.height),s:'blocks mined',ac:'--cyan'},
    {l:'Difficulty',v:d.difficulty,s:('0'.repeat(d.difficulty||0)+'…').slice(0,10)+' target',ac:'--amber'},
    {l:'Next Reward',v:(d.next_reward||0).toFixed(2),s:'POLM per block',ac:'--green'},
    {l:'Epoch',v:d.epoch||0,s:((d.height||0)%100000/1000).toFixed(2)+'% complete',ac:'--purple'},
    {l:'Block Time',v:d.block_time+'s',s:(d.block_time||30)+'s target',ac:'--cyan'},
    {l:'Chain Tip',v:(d.tip_hash||'').slice(0,8)+'…',s:'sha3-256',ac:'--cyan'},
    {l:'Mempool',v:d.mempool_size||0,s:'pending txs',ac:'--amber'},
    {l:'Peers',v:d.peers||0,s:'connected nodes',ac:'--green'},
  ];
  document.getElementById('sg').innerHTML=cards.map(c=>
    `<div class="sc" style="--ac:var(${c.ac})"><div class="sc-l">${c.l}</div><div class="sc-v">${c.v}</div><div class="sc-s">${c.s}</div></div>`
  ).join('');
  const sup=d.total_supply||0,pct=(sup/32000000*100).toFixed(4);
  document.getElementById('sm').textContent=fn(sup.toFixed(0))+' POLM mined';
  document.getElementById('sb').style.width=Math.min(pct,100)+'%';
  document.getElementById('spct2').textContent=pct+'% of max supply';
  document.getElementById('ni').innerHTML=[
    ['Symbol','POLM'],['Max supply','32,000,000'],['Block time','30 seconds'],
    ['Halving','every ~4 years'],['Retarget','every 144 blocks (±25%)'],
    ['Hash algo','SHA3-256'],['Version',d.version||'1.2.0'],
  ].map(([k,v])=>`<div class="irow"><span class="ik">${k}</span><span class="iv">${v}</span></div>`).join('');
}

async function loadMiners(){
  const d=await fetch('/api/miners').then(r=>r.json()).catch(()=>({}));
  const miners=Object.entries(d).sort((a,b)=>b[1].blocks-a[1].blocks);
  const total=miners.reduce((s,[,v])=>s+v.blocks,0);
  document.getElementById('lb-count').textContent=miners.length?`(${miners.length} miners)`:'';
  document.getElementById('lb').innerHTML=miners.slice(0,8).map(([id,v],i)=>{
    const pct=total?(v.blocks/total*100):0,col=RC[v.ram]||'#22d3ee',boost=BOOST[v.ram]||1;
    return`<div class="lrow">
      <div class="rnk ${i<3?'r'+(i+1):''}">${i<3?['①','②','③'][i]:'#'+(i+1)}</div>
      <div class="minfo">
        <div class="maddr">${id.slice(0,24)}…</div>
        <div class="mmeta">${ram(v.ram)}<span style="color:var(--t3)">${(v.avg_latency||0).toFixed(0)}ns avg</span><span style="color:${col}">${(v.reward||0).toFixed(0)} POLM earned</span></div>
      </div>
      <div><div class="bar-wrap"><div class="bar-fill" style="width:${Math.min(pct,100).toFixed(1)}%;background:${col}"></div></div><div class="num mc" style="font-size:.6rem;margin-top:1px">${pct.toFixed(1)}%</div></div>
      <div class="num cc">${v.blocks}</div>
      <div class="num gc">${(v.reward||0).toFixed(0)}</div>
      <div class="num mc">${(v.avg_latency||0).toFixed(0)}ns</div>
      <div class="num" style="color:${col}">${boost}×</div>
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
    const b=item.block||item,col=RC[b.ram_type]||'#22d3ee';
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
}

async function loadRanking(){
  const d=await fetch('/api/miners').then(r=>r.json()).catch(()=>({}));
  const miners=Object.entries(d).sort((a,b)=>b[1].blocks-a[1].blocks);
  const total=miners.reduce((s,[,v])=>s+v.blocks,0);
  const top=miners.slice(0,3);
  const podOrder=top.length>=3?[top[1],top[0],top[2]]:top;
  document.getElementById('podium').innerHTML=podOrder.map((item,pi)=>{
    if(!item) return '<div></div>';
    const [id,v]=item,ri=top.indexOf(item),col=RC[v.ram]||'#22d3ee',pct=total?(v.blocks/total*100):0;
    return`<div class="pod p${ri+1}" style="order:${pi===0?2:pi===1?1:3}">
      <div class="pod-rank">${MEDALS[ri]||'🏅'}</div>
      <div class="pod-addr">${id.slice(0,28)}…</div>
      <div class="pod-ram">${ram(v.ram)} <span style="color:${col};font-family:var(--mono);font-size:.7rem">${BOOST[v.ram]||1}× boost</span></div>
      <div class="pod-blocks" style="color:${col}">${fn(v.blocks)}</div>
      <div class="pod-pct">${pct.toFixed(1)}% of blocks</div>
      <div class="pod-polm">${(v.reward||0).toFixed(0)} POLM</div>
    </div>`;
  }).join('');
  document.getElementById('full-rank').innerHTML=miners.map(([id,v],i)=>{
    const pct=total?(v.blocks/total*100):0,col=RC[v.ram]||'#22d3ee',boost=BOOST[v.ram]||1;
    return`<div class="rrow">
      <div class="rnk ${i<3?'r'+(i+1):''}" style="color:${RK[i]||'var(--t3)'}">#${i+1}</div>
      <div class="minfo"><div class="maddr">${id.slice(0,26)}…</div><div class="mmeta">${ram(v.ram)}</div></div>
      <div><div class="bar-wrap"><div class="bar-fill" style="width:${Math.min(pct,100).toFixed(1)}%;background:${col}"></div></div><div class="num mc" style="font-size:.58rem;margin-top:1px">${pct.toFixed(1)}%</div></div>
      <div class="num cc">${fn(v.blocks)}</div>
      <div class="num gc">${(v.reward||0).toFixed(0)}</div>
      <div class="num ac">${(v.avg_latency||0).toFixed(0)}ns</div>
      <div class="num" style="color:${col}">${boost}×</div>
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
    const b=item.block||item,col=RC[b.ram_type]||'#22d3ee';
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
    ['Symbol','POLM'],['Network',d.network||'mainnet'],['Version',d.version||'1.2.0'],
    ['Height',fn(d.height||0)],['Difficulty',d.difficulty||4],['Epoch',d.epoch||0],
    ['DAG size',(d.dag_size_mb||256)+'MB'],['Max supply','32,000,000 POLM'],
    ['Block time','30 seconds'],['Halving interval','4,200,000 blocks (~4yr)'],
    ['Retarget window','144 blocks (±25%)'],['Founder lock','5,256,000 blocks (~5yr)'],
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
        boost = {"DDR2":10,"DDR3":8,"DDR4":1,"DDR5":0.5}.get(b.get("ram_type","DDR4"), 1)
        txs = item.get("txs", [])
        rows = [
            ("height",       str(b.get("height","")),                  "cyan"),
            ("block hash",   b.get("block_hash",""),                   "cyan"),
            ("prev hash",    b.get("prev_hash",""),                    ""),
            ("timestamp",    f"{b.get('timestamp','')} — {ts}",      ""),
            ("miner",        b.get("miner_id",""),                     "amber"),
            ("RAM type",     b.get("ram_type",""),                     ""),
            ("boost",        f"{boost}× static + dynamic",             "amber"),
            ("threads",      str(b.get("threads","")),                 ""),
            ("epoch",        str(b.get("epoch","")),                   ""),
            ("difficulty",   str(b.get("difficulty","")),              ""),
            ("nonce",        f"{b.get('nonce',0):,}",                ""),
            ("latency proof",f"{b.get('latency_ns',0):.2f} ns",      "amber"),
            ("memory proof", b.get("mem_proof",""),                    ""),
            ("score",        f"{b.get('score',0):,.6f}",             ""),
            ("reward",       f"{b.get('reward',0)} POLM",            "green"),
            ("transactions", str(len(txs)),                            "cyan"),
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
    print(f"  Node: {node_url}\n")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    import sys
    node = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:6060"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5050
    create_explorer(node_url=node, port=port)
