"""
PoLM Explorer v4.0 — Professional Black Edition
Full rankings, live stats, block detail, leaderboard
"""
from flask import Flask, render_template_string, jsonify, request
import json, time, urllib.request

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PoLM Explorer</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#07080a;--s1:#0d1017;--s2:#121820;--s3:#181f2a;
  --b1:#1e2a38;--b2:#263346;
  --cyan:#22d3ee;--cyan2:#0891b2;
  --green:#22c55e;--green2:#16a34a;
  --amber:#f59e0b;--orange:#f97316;
  --purple:#a78bfa;--red:#ef4444;
  --t1:#f0f4f8;--t2:#8ba3bc;--t3:#3d5166;
  --mono:'JetBrains Mono',monospace;
  --sans:'Space Grotesk',sans-serif;
  --r:8px;--r2:12px;
}
html{font-size:13px;scroll-behavior:smooth}
body{background:var(--bg);color:var(--t1);font-family:var(--sans);
  background-image:radial-gradient(ellipse 80% 50% at 50% -5%,rgba(34,211,238,.05) 0%,transparent 65%)}

/* HEADER */
nav{background:rgba(13,16,23,.98);border-bottom:1px solid var(--b1);
  height:54px;display:flex;align-items:center;padding:0 24px;gap:16px;
  position:sticky;top:0;z-index:999;backdrop-filter:blur(16px)}
.logo{font-family:var(--mono);font-weight:700;font-size:1rem;color:var(--cyan);letter-spacing:.04em;white-space:nowrap}
.logo em{color:var(--t3);font-style:normal;font-weight:300}
.pill{padding:3px 10px;border-radius:20px;font-size:.6rem;font-family:var(--mono);font-weight:500}
.pill-net{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.2);color:var(--green);
  display:flex;align-items:center;gap:5px}
.pill-net::before{content:'';width:5px;height:5px;border-radius:50%;background:var(--green);animation:p 2s infinite}
@keyframes p{0%,100%{opacity:1}50%{opacity:.2}}
.nav-tabs{display:flex;gap:2px;margin-left:12px}
.tab{padding:5px 14px;border-radius:6px;font-size:.72rem;cursor:pointer;color:var(--t2);
  border:1px solid transparent;transition:all .15s;font-family:var(--mono)}
.tab:hover{color:var(--t1);background:var(--s2)}
.tab.active{color:var(--cyan);background:rgba(34,211,238,.08);border-color:rgba(34,211,238,.15)}
.nav-right{margin-left:auto;display:flex;align-items:center;gap:10px}
#ts{font-size:.6rem;color:var(--t3);font-family:var(--mono)}
.rbtn{background:transparent;border:1px solid var(--b1);color:var(--t2);
  padding:5px 12px;border-radius:6px;cursor:pointer;font-family:var(--mono);font-size:.65rem;transition:all .15s}
.rbtn:hover{border-color:var(--cyan);color:var(--cyan)}

/* LAYOUT */
.page{display:none;max-width:1480px;margin:0 auto;padding:20px 18px}
.page.active{display:block}

/* SEARCH */
.sbar{display:flex;gap:8px;margin-bottom:20px;max-width:580px}
.sbar input{flex:1;background:var(--s1);border:1px solid var(--b1);border-radius:var(--r);
  padding:9px 14px;color:var(--t1);font-family:var(--mono);font-size:.8rem;outline:none;transition:border-color .15s}
.sbar input:focus{border-color:var(--cyan)}
.sbar input::placeholder{color:var(--t3)}
.sbar button{background:var(--cyan);border:none;color:#000;padding:9px 18px;
  border-radius:var(--r);cursor:pointer;font-family:var(--sans);font-size:.75rem;font-weight:600;transition:background .15s}
.sbar button:hover{background:var(--cyan2);color:#fff}

/* STAT CARDS */
.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin-bottom:18px}
.sc{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:14px;
  position:relative;overflow:hidden;transition:border-color .15s;cursor:default}
.sc::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:var(--ac,var(--cyan));opacity:.5}
.sc:hover{border-color:var(--b2)}
.sc-l{font-size:.58rem;color:var(--t3);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px;font-family:var(--mono)}
.sc-v{font-size:1.2rem;font-weight:700;color:var(--t1);font-family:var(--mono);line-height:1.1}
.sc-s{font-size:.6rem;color:var(--t3);margin-top:3px;font-family:var(--mono)}

/* SECTIONS */
.sec{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);padding:18px;margin-bottom:14px}
.st{font-size:.6rem;font-weight:600;letter-spacing:.15em;text-transform:uppercase;
  color:var(--t2);margin-bottom:14px;display:flex;align-items:center;gap:8px;font-family:var(--mono)}
.st::after{content:'';flex:1;height:1px;background:var(--b1)}
.st span{color:var(--t3);font-size:.58rem;font-weight:400;letter-spacing:0;text-transform:none;margin-left:4px}

/* TWO COL */
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
@media(max-width:900px){.two{grid-template-columns:1fr}}

/* SUPPLY */
.sup-wrap{margin-top:8px}
.sup-row{display:flex;justify-content:space-between;font-size:.75rem;font-family:var(--mono);margin-bottom:5px}
.sup-bar{height:6px;background:var(--s3);border-radius:3px;overflow:hidden;margin:4px 0 8px}
.sup-fill{height:100%;background:linear-gradient(90deg,var(--cyan2),var(--cyan));border-radius:3px;transition:width 1s}
.sup-meta{display:flex;justify-content:space-between;font-size:.6rem;color:var(--t3);font-family:var(--mono)}

/* LEADERBOARD */
.lb-hdr{display:grid;grid-template-columns:28px 1fr 90px 60px 70px 52px 44px;
  gap:8px;padding:0 0 8px;border-bottom:1px solid var(--b1);margin-bottom:4px}
.lb-hdr span{font-size:.58rem;color:var(--t3);text-transform:uppercase;letter-spacing:.1em;font-family:var(--mono)}
.lb-hdr span:not(:first-child){text-align:right}
.lb-hdr span:nth-child(2){text-align:left}
.lrow{display:grid;grid-template-columns:28px 1fr 90px 60px 70px 52px 44px;
  align-items:center;gap:8px;padding:9px 0;border-bottom:1px solid rgba(30,42,56,.5);transition:background .1s}
.lrow:last-child{border-bottom:none}
.lrow:hover{background:rgba(34,211,238,.02)}
.rnk{font-family:var(--mono);font-size:.72rem;font-weight:700;color:var(--t3);text-align:center}
.rnk.r1{color:#fbbf24}.rnk.r2{color:#9ca3af}.rnk.r3{color:#cd7f32}
.minfo{min-width:0}
.maddr{font-family:var(--mono);font-size:.72rem;color:var(--cyan);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:pointer}
.maddr:hover{text-decoration:underline}
.mmeta{font-size:.6rem;color:var(--t3);margin-top:2px;font-family:var(--mono);display:flex;align-items:center;gap:6px}
.bar-wrap{position:relative;height:4px;background:var(--s3);border-radius:2px;overflow:hidden}
.bar-fill{height:100%;border-radius:2px;transition:width .6s}
.num{font-family:var(--mono);font-size:.72rem;text-align:right;white-space:nowrap}
.gc{color:var(--green)}.ac{color:var(--amber)}.cc{color:var(--cyan)}.mc{color:var(--t3)}.rc{color:var(--red)}
.trend{font-size:.65rem;font-family:var(--mono)}

/* RAM BADGE */
.ram{display:inline-block;padding:2px 7px;border-radius:4px;font-size:.6rem;font-weight:700;font-family:var(--mono)}
.ddr2{background:rgba(249,115,22,.1);color:#fb923c;border:1px solid rgba(249,115,22,.2)}
.ddr3{background:rgba(245,158,11,.08);color:#fbbf24;border:1px solid rgba(245,158,11,.18)}
.ddr4{background:rgba(34,211,238,.07);color:var(--cyan);border:1px solid rgba(34,211,238,.14)}
.ddr5{background:rgba(239,68,68,.08);color:#f87171;border:1px solid rgba(239,68,68,.15)}

/* BOOST CARDS */
.bgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}
@media(max-width:600px){.bgrid{grid-template-columns:repeat(2,1fr)}}
.bc{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);padding:14px;text-align:center;transition:border-color .15s}
.bc:hover{border-color:var(--b2)}
.bt{font-family:var(--mono);font-size:.95rem;font-weight:700;margin-bottom:3px}
.bm{font-size:1.5rem;font-weight:700;font-family:var(--mono);margin-bottom:2px}
.bs{font-size:.58rem;color:var(--t3);font-family:var(--mono)}
.bpen{font-size:.58rem;margin-top:3px;font-family:var(--mono)}
.b2 .bt,.b2 .bm{color:#fb923c}
.b3 .bt,.b3 .bm{color:#fbbf24}
.b4 .bt,.b4 .bm{color:var(--cyan)}
.b5 .bt,.b5 .bm{color:#f87171}

/* BLOCK TABLE */
table{width:100%;border-collapse:collapse;font-size:.72rem}
th{text-align:left;padding:7px 10px;color:var(--t3);font-size:.58rem;letter-spacing:.1em;
  text-transform:uppercase;border-bottom:1px solid var(--b1);font-family:var(--mono);font-weight:400;white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid rgba(30,42,56,.4);vertical-align:middle;font-family:var(--mono)}
tbody tr{cursor:pointer;transition:background .1s}
tbody tr:hover td{background:rgba(34,211,238,.025)}
tbody tr:last-child td{border-bottom:none}
a.hl{color:var(--cyan);text-decoration:none}
a.hl:hover{text-decoration:underline}

/* NET INFO */
.irow{display:flex;justify-content:space-between;align-items:center;
  padding:7px 0;border-bottom:1px solid rgba(30,42,56,.4);font-size:.75rem}
.irow:last-child{border-bottom:none}
.ik{color:var(--t3);font-family:var(--mono)}.iv{color:var(--t1);font-family:var(--mono);font-weight:500}

/* RANKING PAGE */
.rank-hero{background:var(--s1);border:1px solid var(--b1);border-radius:var(--r2);
  padding:24px;margin-bottom:14px;text-align:center}
.rank-hero h2{font-size:1.2rem;font-weight:700;margin-bottom:6px;font-family:var(--mono);color:var(--cyan)}
.rank-hero p{font-size:.75rem;color:var(--t2);font-family:var(--mono)}
.podium{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:20px 0}
.pod{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r2);padding:16px;text-align:center;transition:border-color .2s}
.pod:hover{border-color:var(--b2)}
.pod.p1{border-color:rgba(251,191,36,.3);background:rgba(251,191,36,.04)}
.pod.p2{border-color:rgba(156,163,175,.2)}
.pod.p3{border-color:rgba(205,127,50,.2)}
.pod-rank{font-size:1.8rem;margin-bottom:8px}
.pod-addr{font-family:var(--mono);font-size:.68rem;color:var(--cyan);margin-bottom:6px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pod-blocks{font-family:var(--mono);font-size:1.6rem;font-weight:700;color:var(--t1)}
.pod-pct{font-size:.7rem;color:var(--t3);font-family:var(--mono)}
.pod-polm{font-size:.8rem;color:var(--green);font-family:var(--mono);margin-top:4px}

/* PENALTY TABLE */
.pen-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:6px}
.pen-card{background:var(--s2);border:1px solid var(--b1);border-radius:var(--r);padding:10px;text-align:center}
.pen-t{font-size:.65rem;color:var(--t2);font-family:var(--mono);margin-bottom:4px}
.pen-v{font-size:1rem;font-weight:700;font-family:var(--mono);color:var(--amber)}

/* FOOTER */
footer{border-top:1px solid var(--b1);padding:14px 24px;
  display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-top:8px}
.fl{font-size:.6rem;color:var(--t3);font-family:var(--mono)}
.fl a{color:var(--cyan);text-decoration:none}
</style>
</head>
<body>

<nav>
  <div class="logo">PoLM <em>/</em> Explorer</div>
  <div class="pill pill-net">testnet</div>
  <div class="nav-tabs">
    <div class="tab active" onclick="showPage('dashboard',this)">Dashboard</div>
    <div class="tab" onclick="showPage('ranking',this)">Ranking</div>
    <div class="tab" onclick="showPage('blocks',this)">Blocks</div>
    <div class="tab" onclick="showPage('protocol',this)">Protocol</div>
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
      <div class="sup-row">
        <span id="sm" style="color:var(--cyan)"></span>
        <span style="color:var(--t3)">/ 32,000,000 POLM max</span>
      </div>
      <div class="sup-bar"><div class="sup-fill" id="sb" style="width:0%"></div></div>
      <div class="sup-meta"><span id="spct2"></span><span>halving ~4yr · 5.0 POLM initial reward</span></div>
    </div>
  </div>
  <div class="two">
    <div class="sec">
      <div class="st">Live leaderboard</div>
      <div class="lb-hdr">
        <span>#</span><span>Miner</span><span>Share</span>
        <span>Blocks</span><span>POLM</span><span>Lat</span><span>Boost</span>
      </div>
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
          <div class="bc b2">
            <div class="bt">DDR2</div><div class="bm">10×</div>
            <div class="bs">80 steps/nonce</div>
            <div class="bpen" style="color:var(--green)">max legacy</div>
          </div>
          <div class="bc b3">
            <div class="bt">DDR3</div><div class="bm">5×</div>
            <div class="bs">150 steps/nonce</div>
            <div class="bpen" style="color:var(--amber)">legacy bonus</div>
          </div>
          <div class="bc b4">
            <div class="bt">DDR4</div><div class="bm">1×</div>
            <div class="bs">500 steps/nonce</div>
            <div class="bpen" style="color:var(--t3)">baseline</div>
          </div>
          <div class="bc b5">
            <div class="bt">DDR5</div><div class="bm">0×</div>
            <div class="bs">700 steps/nonce</div>
            <div class="bpen" style="color:var(--red)">blocked</div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <div class="sec">
    <div class="st">Latest blocks <span id="blk-count"></span></div>
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>Height</th><th>Hash</th><th>Miner</th><th>RAM</th>
        <th>Latency</th><th>Score</th><th>Nonce</th><th>Reward</th><th>Age</th>
      </tr></thead>
      <tbody id="bb"></tbody>
    </table>
    </div>
  </div>
</div>
</div>

<!-- RANKING -->
<div class="page" id="page-ranking">
<div style="max-width:1480px;margin:0 auto;padding:20px 18px">
  <div class="rank-hero">
    <h2>⛏ Mining Leaderboard</h2>
    <p>Ranked by blocks mined · Updated every 8s · Legacy hardware rewarded</p>
    <div class="podium" id="podium"></div>
  </div>
  <div class="sec">
    <div class="st">Full rankings</div>
    <div class="lb-hdr">
      <span>#</span><span>Miner</span><span>Share</span>
      <span>Blocks</span><span>POLM</span><span>Lat</span><span>Boost</span>
    </div>
    <div id="lb2"></div>
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
  <div class="sec">
    <div class="st">All blocks <span id="blk-count2"></span></div>
    <div style="overflow-x:auto">
    <table>
      <thead><tr>
        <th>Height</th><th>Hash</th><th>Miner</th><th>RAM</th>
        <th>Latency</th><th>Score</th><th>Nonce</th><th>Reward</th><th>Age</th>
      </tr></thead>
      <tbody id="bb2"></tbody>
    </table>
    </div>
    <div style="text-align:center;margin-top:12px">
      <button class="rbtn" onclick="loadMore()" id="load-more">Load 50 more</button>
    </div>
  </div>
</div>
</div>

<!-- PROTOCOL -->
<div class="page" id="page-protocol">
<div style="max-width:1480px;margin:0 auto;padding:20px 18px">
  <div class="two">
    <div class="sec">
      <div class="st">Protocol parameters</div>
      <div id="proto-params"></div>
    </div>
    <div class="sec">
      <div class="st">Security model</div>
      <div id="proto-sec"></div>
    </div>
  </div>
  <div class="sec">
    <div class="st">Algorithm flow</div>
    <div style="font-family:var(--mono);font-size:.75rem;color:var(--t2);line-height:2;padding:8px 0">
      <div style="color:var(--cyan)">getwork()</div>
      <div style="padding-left:16px">↓</div>
      <div style="padding-left:16px">Build Memory DAG <span style="color:var(--t3)">(seeded from epoch + prev_hash)</span></div>
      <div style="padding-left:16px">↓</div>
      <div style="padding-left:16px">Random Memory Walk <span style="color:var(--t3)">(N steps — adaptive per RAM type)</span></div>
      <div style="padding-left:32px;color:var(--t3)">├─ pos = sha3(H_prev) % DAG_size</div>
      <div style="padding-left:32px;color:var(--t3)">├─ read 32 bytes from DAG[pos]</div>
      <div style="padding-left:32px;color:var(--t3)">├─ H_new = sha3(H_prev ∥ DAG[pos])</div>
      <div style="padding-left:32px;color:var(--t3)">└─ measure latency (nanoseconds)</div>
      <div style="padding-left:16px">↓</div>
      <div style="padding-left:16px">Apply Legacy Boost × Saturation Penalty</div>
      <div style="padding-left:16px">↓</div>
      <div style="padding-left:16px;color:var(--green)">submit() → validate → add to chain</div>
    </div>
  </div>
  <div class="sec">
    <div class="st">Boost calibration <span>from testnet measurements Mar 2026</span></div>
    <div class="bgrid">
      <div class="bc b2">
        <div class="bt">DDR2</div><div class="bm">10×</div>
        <div class="bs">~6700–8000 ns</div><div class="bs">80 steps/nonce</div>
        <div class="bpen" style="color:var(--green);margin-top:6px">Max legacy bonus</div>
      </div>
      <div class="bc b3">
        <div class="bt">DDR3</div><div class="bm">5×</div>
        <div class="bs">~1500–3000 ns</div><div class="bs">150 steps/nonce</div>
        <div class="bpen" style="color:var(--amber);margin-top:6px">Strong legacy bonus</div>
      </div>
      <div class="bc b4">
        <div class="bt">DDR4</div><div class="bm">1×</div>
        <div class="bs">~900–1700 ns</div><div class="bs">500 steps/nonce</div>
        <div class="bpen" style="color:var(--t3);margin-top:6px">Baseline</div>
      </div>
      <div class="bc b5">
        <div class="bt">DDR5</div><div class="bm">0×</div>
        <div class="bs">~500–900 ns</div><div class="bs">700 steps/nonce</div>
        <div class="bpen" style="color:var(--red);margin-top:6px">Blocked</div>
      </div>
    </div>
  </div>
</div>
</div>

<footer>
  <div class="fl">PoLM v3.1.0 &nbsp;·&nbsp; Proof of Legacy Memory &nbsp;·&nbsp; MIT License &nbsp;·&nbsp; Experimental Testnet</div>
  <div class="fl"><a href="https://github.com/proof-of-legacy/Proof-of-Legacy-Memory">github.com/proof-of-legacy/Proof-of-Legacy-Memory</a></div>
</footer>

<script>
const B={DDR2:10,DDR3:5,DDR4:1,DDR5:0};
const RC={DDR2:'#fb923c',DDR3:'#fbbf24',DDR4:'#22d3ee',DDR5:'#f87171'};
const POD=['🥇','🥈','🥉'];
let offset=0, allMiners={}, allSummary={};

function showPage(id,el){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('page-'+id).classList.add('active');
  if(el) el.classList.add('active');
  if(id==='blocks'){offset=0;loadBlocks(50,0,true);}
}

async function load(){
  try{
    const[s,bl,m]=await Promise.all([
      fetch('/api/summary').then(r=>r.json()),
      fetch('/api/blocks?limit=30').then(r=>r.json()),
      fetch('/api/miners').then(r=>r.json()),
    ]);
    allMiners=m; allSummary=s;
    rStats(s); rSupply(s); rLeader(m,'lb'); rNet(s); rBlocks(bl,'bb');
    rPodium(m); rLeader(m,'lb2');
    document.getElementById('blk-count').textContent='showing 30 of '+(s.height+1);
    document.getElementById('blk-count2').textContent='showing '+(offset+Math.min(50,s.height+1))+' of '+(s.height+1);
    document.getElementById('ts').textContent=new Date().toLocaleTimeString();
    rProto(s);
  }catch(e){console.error(e)}
}

function rStats(s){
  const ep=((s.height%100000)/100000*100).toFixed(2);
  const items=[
    {l:'Height',v:s.height.toLocaleString(),s:'blocks mined',a:'var(--cyan)'},
    {l:'Difficulty',v:s.difficulty,s:'0'.repeat(s.difficulty)+'… target',a:'var(--amber)'},
    {l:'Next Reward',v:s.next_reward.toFixed(2),s:'POLM per block',a:'var(--green)'},
    {l:'Epoch',v:s.epoch,s:ep+'% complete',a:'var(--purple)'},
    {l:'Block Time',v:s.block_time+'s',s:'30s target',a:'var(--orange)'},
    {l:'Chain Tip',v:s.tip_hash.slice(0,8)+'…',s:'sha3-256',a:'var(--cyan)'},
  ];
  document.getElementById('sg').innerHTML=items.map(i=>
    `<div class="sc" style="--ac:${i.a}">
      <div class="sc-l">${i.l}</div>
      <div class="sc-v">${i.v}</div>
      <div class="sc-s">${i.s}</div>
    </div>`).join('');
}

function rSupply(s){
  const p=(s.total_supply/s.max_supply*100);
  document.getElementById('sm').textContent=Number(s.total_supply).toLocaleString('en',{maximumFractionDigits:0})+' POLM mined';
  document.getElementById('sb').style.width=Math.min(p,100).toFixed(8)+'%';
  document.getElementById('spct').textContent='('+p.toFixed(4)+'%)';
  document.getElementById('spct2').textContent=p.toFixed(6)+'% of max supply';
}

function rb(r){
  const c={DDR2:'ddr2',DDR3:'ddr3',DDR4:'ddr4',DDR5:'ddr5'}[r]||'ddr4';
  return`<span class="ram ${c}">${r}</span>`;
}

function age(ts){
  const d=Math.floor(Date.now()/1000)-ts;
  if(d<60)return d+'s';
  if(d<3600)return Math.floor(d/60)+'m'+Math.floor(d%60)+'s';
  return Math.floor(d/3600)+'h'+Math.floor((d%3600)/60)+'m';
}

function rLeader(m,id){
  const s=Object.entries(m).sort((a,b)=>b[1].blocks-a[1].blocks);
  const t=s.reduce((x,[,v])=>x+v.blocks,0);
  const rk=['r1','r2','r3'];
  document.getElementById(id).innerHTML=s.map(([addr,v],i)=>{
    const p=t?(v.blocks/t*100):0;
    const boost=B[v.ram]||1;
    const col=RC[v.ram]||'#22d3ee';
    return`<div class="lrow">
      <div class="rnk ${rk[i]||''}">${i+1}</div>
      <div class="minfo">
        <div class="maddr" onclick="searchAddr('${addr}')" title="${addr}">${addr.slice(0,24)}…</div>
        <div class="mmeta">${rb(v.ram)}<span>${v.avg_latency.toFixed(0)}ns avg</span><span>${v.reward.toFixed(0)} POLM earned</span></div>
      </div>
      <div>
        <div class="bar-wrap"><div class="bar-fill" style="width:${Math.min(p,100).toFixed(1)}%;background:${col}"></div></div>
        <div style="font-size:.6rem;color:var(--t3);font-family:var(--mono);margin-top:2px;text-align:right">${p.toFixed(1)}%</div>
      </div>
      <div class="num cc">${v.blocks.toLocaleString()}</div>
      <div class="num gc">${v.reward.toFixed(0)}</div>
      <div class="num mc">${v.avg_latency.toFixed(0)}ns</div>
      <div class="num ac">${boost}×</div>
    </div>`;
  }).join('');
}

function rPodium(m){
  const s=Object.entries(m).sort((a,b)=>b[1].blocks-a[1].blocks).slice(0,3);
  const t=Object.values(m).reduce((x,v)=>x+v.blocks,0);
  document.getElementById('podium').innerHTML=s.map(([addr,v],i)=>{
    const p=t?(v.blocks/t*100):0;
    const col=RC[v.ram]||'#22d3ee';
    return`<div class="pod p${i+1}" style="border-color:${i===0?'rgba(251,191,36,.4)':i===1?'rgba(156,163,175,.25)':'rgba(205,127,50,.25)'}">
      <div class="pod-rank">${POD[i]}</div>
      <div class="pod-addr" style="color:${col}">${addr.slice(0,20)}…</div>
      <div style="margin:6px 0">${rb(v.ram)} <span style="font-size:.65rem;font-family:var(--mono);color:var(--amber)">${B[v.ram]||1}× boost</span></div>
      <div class="pod-blocks">${v.blocks.toLocaleString()}</div>
      <div class="pod-pct">${p.toFixed(1)}% of blocks</div>
      <div class="pod-polm">${v.reward.toFixed(0)} POLM</div>
    </div>`;
  }).join('');
}

function rNet(s){
  const rows=[
    ['Symbol','POLM'],['Max supply','32,000,000'],['Block time','30 seconds'],
    ['Halving','every ~4 years'],['Retarget','every 144 blocks (±25%)'],
    ['Hash algo','SHA3-256'],['Version','v3.1.0'],
  ];
  document.getElementById('ni').innerHTML=rows.map(([k,v])=>
    `<div class="irow"><span class="ik">${k}</span><span class="iv">${v}</span></div>`).join('');
}

function rBlocks(bl,id){
  if(!bl.length){document.getElementById(id).innerHTML='<tr><td colspan="9" style="text-align:center;padding:28px;color:var(--t3)">No blocks</td></tr>';return;}
  document.getElementById(id).innerHTML=bl.map(b=>{
    const c=RC[b.ram_type]||'#22d3ee';
    return`<tr onclick="window.location='/block/${b.height}'">
      <td style="color:${c};font-weight:600">${b.height}</td>
      <td><a class="hl" href="/block/${b.height}" onclick="event.stopPropagation()">${b.block_hash.slice(0,14)}…</a></td>
      <td style="color:var(--t2);max-width:130px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${b.miner_id}">${b.miner_id.slice(0,16)}…</td>
      <td>${rb(b.ram_type)}</td>
      <td style="color:var(--t3)">${Number(b.latency_ns).toFixed(0)}ns</td>
      <td style="color:var(--amber)">${Number(b.score).toLocaleString('en',{maximumFractionDigits:0})}</td>
      <td style="color:var(--t3)">${Number(b.nonce).toLocaleString()}</td>
      <td style="color:var(--green)">${b.reward.toFixed(1)}</td>
      <td style="color:var(--t3)">${age(b.timestamp)}</td>
    </tr>`;}).join('');
}

function rProto(s){
  const params=[
    ['Symbol','POLM'],['Max supply','32,000,000'],['Block time','30s target'],
    ['Initial reward','5.0 POLM'],['Halving','every ~4,200,000 blocks'],
    ['Difficulty retarget','every 144 blocks'],['Max adjustment','±25% per window'],
    ['Epoch length','100,000 blocks'],['Hash algorithm','SHA3-256'],
    ['Current height',s.height.toLocaleString()],['Current difficulty',s.difficulty],
  ];
  const sec=[
    ['ASIC','Large DAG + latency — DRAM physics cannot be miniaturized'],
    ['GPU','GDDR latency > DDR latency — no bandwidth advantage'],
    ['Cache exploit','Latency < 5ns → block rejected by all nodes'],
    ['Fake RAM','Latency embedded in block header — verified on submit'],
    ['DDR5','Boost = 0× — effectively blocked from mining'],
    ['Replay','Commits to prev_hash + timestamp + nonce'],
  ];
  document.getElementById('proto-params').innerHTML=params.map(([k,v])=>
    `<div class="irow"><span class="ik">${k}</span><span class="iv">${v}</span></div>`).join('');
  document.getElementById('proto-sec').innerHTML=sec.map(([k,v])=>
    `<div class="irow"><span class="ik" style="color:var(--red)">${k}</span><span class="iv" style="color:var(--t2);font-size:.68rem;text-align:right;max-width:200px">${v}</span></div>`).join('');
}

async function loadBlocks(limit,off,replace){
  const bl=await fetch(`/api/blocks?limit=${limit}&offset=${off}`).then(r=>r.json());
  if(replace){
    rBlocks(bl,'bb2');
  } else {
    document.getElementById('bb2').innerHTML+=bl.map(b=>{
      const c=RC[b.ram_type]||'#22d3ee';
      return`<tr onclick="window.location='/block/${b.height}'">
        <td style="color:${c};font-weight:600">${b.height}</td>
        <td><a class="hl" href="/block/${b.height}">${b.block_hash.slice(0,14)}…</a></td>
        <td style="color:var(--t2)">${b.miner_id.slice(0,16)}…</td>
        <td>${rb(b.ram_type)}</td>
        <td style="color:var(--t3)">${Number(b.latency_ns).toFixed(0)}ns</td>
        <td style="color:var(--amber)">${Number(b.score).toLocaleString('en',{maximumFractionDigits:0})}</td>
        <td style="color:var(--t3)">${Number(b.nonce).toLocaleString()}</td>
        <td style="color:var(--green)">${b.reward.toFixed(1)}</td>
        <td style="color:var(--t3)">${age(b.timestamp)}</td>
      </tr>`;}).join('');
  }
}

function loadMore(){
  offset+=50;
  loadBlocks(50,offset,false);
}

function searchAddr(addr){
  document.getElementById('q').value=addr;
  showPage('dashboard',document.querySelector('.tab'));
}

function go(){
  const q=document.getElementById('q').value.trim();
  if(!q)return;
  if(/^[0-9]+$/.test(q)){window.location='/block/'+q;return;}
  if(q.length===64){window.location='/block/hash/'+q;return;}
  alert('Enter a valid block height or 64-char hash');
}

load();
setInterval(load,8000);
</script>
</body>
</html>"""

BLOCK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Block #{{ height }} — PoLM Explorer</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#07080a;--s1:#0d1017;--b1:#1e2a38;--cyan:#22d3ee;--green:#22c55e;--amber:#f59e0b;--red:#ef4444;--t1:#f0f4f8;--t2:#8ba3bc;--t3:#3d5166;--mono:'JetBrains Mono',monospace;--sans:'Space Grotesk',sans-serif}
body{background:var(--bg);color:var(--t1);font-family:var(--sans);padding:28px;min-height:100vh}
a.back{color:var(--cyan);text-decoration:none;font-size:.78rem;font-family:var(--mono);display:inline-flex;align-items:center;gap:6px;margin-bottom:20px;padding:6px 12px;border:1px solid var(--b1);border-radius:6px;transition:border-color .15s}
a.back:hover{border-color:var(--cyan)}
.hdr{display:flex;align-items:center;gap:12px;margin-bottom:20px}
h1{font-size:1.3rem;font-weight:700;font-family:var(--mono);color:var(--cyan)}
.card{background:var(--s1);border:1px solid var(--b1);border-radius:12px;overflow:hidden}
.row{display:flex;justify-content:space-between;gap:16px;padding:11px 20px;border-bottom:1px solid var(--b1);font-size:.78rem}
.row:last-child{border-bottom:none}
.row:hover{background:rgba(34,211,238,.02)}
.k{color:var(--t3);font-family:var(--mono);min-width:140px;flex-shrink:0;font-size:.72rem;letter-spacing:.04em}
.v{color:var(--t1);font-family:var(--mono);word-break:break-all;text-align:right}
.cyan{color:var(--cyan)}.green{color:var(--green)}.amber{color:var(--amber)}.red{color:var(--red)}
</style>
</head>
<body>
<a class="back" href="/">← Explorer</a>
<div class="hdr">
  <h1>Block #{{ height }}</h1>
</div>
<div class="card">
{% for key, val, cls in rows %}
<div class="row"><span class="k">{{ key }}</span><span class="v {{ cls }}">{{ val }}</span></div>
{% endfor %}
</div>
</body>
</html>"""


def create_explorer(node_url="http://localhost:6060", port=5050):
    app = Flask("polm-explorer-v4")

    def fetch(path):
        try:
            r = urllib.request.urlopen(f"{node_url}{path}", timeout=5)
            return json.loads(r.read())
        except:
            return None

    @app.route("/")
    def index():
        return HTML

    @app.route("/api/summary")
    def api_summary():
        d = fetch("/")
        return app.response_class(json.dumps(d or {"error":"offline"}), mimetype='application/json')

    @app.route("/api/blocks")
    def api_blocks():
        limit = int(request.args.get("limit", 30))
        offset = int(request.args.get("offset", 0))
        d = fetch(f"/chain?limit={limit}&offset={offset}")
        return app.response_class(json.dumps(d or []), mimetype='application/json')

    @app.route("/api/miners")
    def api_miners():
        d = fetch("/miners")
        return app.response_class(json.dumps(d or {}), mimetype='application/json')

    @app.route("/block/<int:h>")
    def block_detail(h):
        b = fetch(f"/block/{h}")
        if not b:
            return "Block not found", 404
        ts = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(b["timestamp"]))
        boost = {RAMType: mult for RAMType, mult in [("DDR2",10),("DDR3",5),("DDR4",1),("DDR5",0)]}.get(b["ram_type"], 1)
        rows = [
            ("height",       str(b["height"]),                           "cyan"),
            ("block hash",   b["block_hash"],                            "cyan"),
            ("prev hash",    b["prev_hash"],                             ""),
            ("timestamp",    f"{b['timestamp']} — {ts}",                 ""),
            ("miner",        b["miner_id"],                              "amber"),
            ("RAM type",     b["ram_type"],                              ""),
            ("boost",        f"{boost}×",                                "amber"),
            ("threads",      str(b["threads"]),                          ""),
            ("epoch",        str(b["epoch"]),                            ""),
            ("difficulty",   str(b["difficulty"]),                       ""),
            ("nonce",        f"{b['nonce']:,}",                         ""),
            ("latency proof",f"{b['latency_ns']:.2f} ns",               "amber"),
            ("memory proof", b["mem_proof"],                             ""),
            ("score",        f"{b['score']:,.0f}",                      ""),
            ("reward",       f"{b['reward']} POLM",                     "green"),
        ]
        return render_template_string(BLOCK_HTML, height=h, rows=rows)

    @app.route("/block/hash/<h>")
    def block_by_hash(h):
        blocks = fetch("/chain?limit=500") or []
        for b in blocks:
            if b.get("block_hash") == h:
                return block_detail(b["height"])
        return "Block not found", 404

    print(f"\n[Explorer] PoLM Explorer v4.0 Professional")
    print(f"[Explorer] Node: {node_url}")
    print(f"[Explorer] http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    import sys
    node = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:6060"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5050
    create_explorer(node_url=node, port=port)
