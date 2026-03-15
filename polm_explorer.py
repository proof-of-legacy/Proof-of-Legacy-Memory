"""
PoLM Explorer v3.1
Web explorer para a blockchain PoLM
Conecta ao nó central via API REST
"""

from flask import Flask, render_template_string, jsonify, request
import json, time, os

EXPLORER_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PoLM Explorer</title>
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<style>
:root {
  --bg:      #090e14;
  --surf:    #0f1923;
  --surf2:   #162130;
  --border:  #1e3448;
  --accent:  #00e5ff;
  --green:   #00ff88;
  --amber:   #ffb300;
  --orange:  #ff6b35;
  --text:    #c8dff0;
  --muted:   #4a6a8a;
  --mono:    'Share Tech Mono', monospace;
  --disp:    'Orbitron', monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:var(--mono);font-size:13px;
  background-image:repeating-linear-gradient(0deg,transparent,transparent 39px,rgba(0,229,255,0.015) 40px),
  repeating-linear-gradient(90deg,transparent,transparent 39px,rgba(0,229,255,0.015) 40px);}
body::after{content:'';pointer-events:none;position:fixed;inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.04) 3px);z-index:9999;}

header{border-bottom:1px solid var(--border);padding:16px 28px;display:flex;align-items:center;gap:20px;
  background:rgba(15,25,35,0.97);position:sticky;top:0;z-index:100;backdrop-filter:blur(10px);}
.logo{font-family:var(--disp);font-size:1.3rem;font-weight:900;letter-spacing:.12em;color:var(--accent);
  text-shadow:0 0 18px rgba(0,229,255,.4);}
.logo b{color:var(--green)}
.tagline{font-size:.7rem;color:var(--muted);letter-spacing:.1em}
.dot{width:7px;height:7px;border-radius:50%;background:var(--green);box-shadow:0 0 7px var(--green);
  margin-left:auto;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.25}}

main{max-width:1300px;margin:0 auto;padding:24px 20px}

.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:28px}
.stat{background:var(--surf);border:1px solid var(--border);border-radius:6px;padding:14px 18px;
  position:relative;overflow:hidden;transition:border-color .2s}
.stat::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,var(--accent),transparent);opacity:.4}
.stat:hover{border-color:var(--accent)}
.stat-label{font-size:.65rem;color:var(--muted);letter-spacing:.12em;text-transform:uppercase;margin-bottom:6px}
.stat-value{font-family:var(--disp);font-size:1.3rem;font-weight:700;color:var(--accent)}
.stat-unit{font-size:.65rem;color:var(--muted);margin-top:2px}

.section-title{font-family:var(--disp);font-size:.7rem;letter-spacing:.2em;color:var(--muted);
  text-transform:uppercase;margin-bottom:10px;padding-bottom:7px;border-bottom:1px solid var(--border)}

.leaderboard{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;margin-bottom:28px}
.miner-card{background:var(--surf);border:1px solid var(--border);border-radius:6px;padding:14px 18px}
.miner-card.winner{border-color:var(--amber)}
.miner-name{font-size:.8rem;color:var(--accent);margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.miner-stats{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.ms{font-size:.7rem}
.ms-label{color:var(--muted)}
.ms-value{color:var(--text);font-weight:700}
.badge{display:inline-block;padding:2px 7px;border-radius:3px;font-size:.65rem;font-weight:700;letter-spacing:.05em}
.ddr2{background:rgba(255,107,53,.12);color:var(--orange);border:1px solid rgba(255,107,53,.25)}
.ddr3{background:rgba(255,179,0,.1);color:var(--amber);border:1px solid rgba(255,179,0,.25)}
.ddr4{background:rgba(0,229,255,.08);color:var(--accent);border:1px solid rgba(0,229,255,.2)}
.ddr5{background:rgba(0,255,136,.08);color:var(--green);border:1px solid rgba(0,255,136,.2)}

.chain-table{width:100%;border-collapse:collapse;margin-bottom:28px}
.chain-table th{text-align:left;padding:9px 12px;color:var(--muted);font-size:.62rem;
  letter-spacing:.14em;text-transform:uppercase;border-bottom:1px solid var(--border)}
.chain-table td{padding:9px 12px;border-bottom:1px solid rgba(30,52,72,.4);vertical-align:middle}
.chain-table tr:hover td{background:rgba(0,229,255,.025);cursor:pointer}
.hash{color:var(--accent);font-size:.75rem}
.hash-muted{color:var(--muted);font-size:.7rem}

.boost-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:28px}
.boost-card{background:var(--surf);border:1px solid var(--border);border-radius:6px;padding:14px;text-align:center}
.boost-type{font-family:var(--disp);font-size:1.1rem;font-weight:700;margin-bottom:4px}
.boost-mult{font-size:1.5rem;font-weight:700;margin-bottom:4px}
.boost-desc{font-size:.62rem;color:var(--muted)}
.boost-card.b2 .boost-type,.boost-card.b2 .boost-mult{color:var(--orange)}
.boost-card.b3 .boost-type,.boost-card.b3 .boost-mult{color:var(--amber)}
.boost-card.b4 .boost-type,.boost-card.b4 .boost-mult{color:var(--accent)}
.boost-card.b5 .boost-type,.boost-card.b5 .boost-mult{color:var(--green)}

.search-row{display:flex;gap:8px;margin-bottom:20px}
.search-row input{flex:1;background:var(--surf);border:1px solid var(--border);border-radius:4px;
  padding:9px 13px;color:var(--text);font-family:var(--mono);font-size:.82rem;outline:none}
.search-row input:focus{border-color:var(--accent)}
.search-row button{background:rgba(0,229,255,.08);border:1px solid var(--accent);color:var(--accent);
  padding:9px 18px;border-radius:4px;cursor:pointer;font-family:var(--disp);font-size:.68rem;
  letter-spacing:.1em;transition:background .2s}
.search-row button:hover{background:rgba(0,229,255,.16)}

footer{border-top:1px solid var(--border);padding:18px 28px;text-align:center;
  color:var(--muted);font-size:.68rem;letter-spacing:.07em}

@media(max-width:700px){
  .boost-grid{grid-template-columns:repeat(2,1fr)}
  .chain-table th:nth-child(3),.chain-table td:nth-child(3),
  .chain-table th:nth-child(6),.chain-table td:nth-child(6){display:none}
}
</style>
</head>
<body>
<header>
  <div>
    <div class="logo">PoLM <b>Explorer</b></div>
    <div class="tagline">Proof of Legacy Memory · RAM-Latency-Bound PoW</div>
  </div>
  <div class="dot" title="Node online"></div>
</header>

<main>
  <div class="search-row">
    <input id="q" placeholder="Block height or hash (64 chars)…" onkeydown="if(event.key==='Enter')search()">
    <button onclick="search()">SEARCH</button>
  </div>

  <div class="stats" id="stats"></div>

  <p class="section-title">Miner leaderboard</p>
  <div class="leaderboard" id="leaderboard"></div>

  <p class="section-title">Legacy boost multipliers</p>
  <div class="boost-grid">
    <div class="boost-card b2"><div class="boost-type">DDR2</div><div class="boost-mult">2.20×</div><div class="boost-desc">Max legacy bonus</div></div>
    <div class="boost-card b3"><div class="boost-type">DDR3</div><div class="boost-mult">1.60×</div><div class="boost-desc">Strong legacy bonus</div></div>
    <div class="boost-card b4"><div class="boost-type">DDR4</div><div class="boost-mult">1.00×</div><div class="boost-desc">Baseline</div></div>
    <div class="boost-card b5"><div class="boost-type">DDR5</div><div class="boost-mult">0.85×</div><div class="boost-desc">Modern penalty</div></div>
  </div>

  <p class="section-title">Latest blocks</p>
  <table class="chain-table">
    <thead><tr>
      <th>#</th><th>Hash</th><th>Prev</th><th>Miner</th><th>RAM</th>
      <th>Score</th><th>Latency</th><th>Reward</th><th>Age</th>
    </tr></thead>
    <tbody id="blocks"></tbody>
  </table>
</main>

<footer>PoLM v3.0.0 &nbsp;·&nbsp; Max supply: 32,000,000 POLM &nbsp;·&nbsp; Experimental Testnet</footer>

<script>
const NODE = '';

async function load() {
  try {
    const [sum, blks, miners] = await Promise.all([
      fetch(NODE+'/api/summary').then(r=>r.json()),
      fetch(NODE+'/api/blocks?limit=20').then(r=>r.json()),
      fetch(NODE+'/api/miners').then(r=>r.json()),
    ]);
    renderStats(sum);
    renderLeaderboard(miners);
    renderBlocks(blks);
  } catch(e) { console.error(e); }
}

function renderStats(s) {
  const items = [
    {label:'Block Height', value:s.height.toLocaleString(), unit:'blocks'},
    {label:'Total Supply', value:Number(s.total_supply).toLocaleString('en',{maximumFractionDigits:0}), unit:`/ 32,000,000 POLM`},
    {label:'Next Reward', value:s.next_reward.toFixed(2), unit:'POLM'},
    {label:'Difficulty', value:s.difficulty, unit:'leading zeros'},
    {label:'Epoch', value:s.epoch, unit:'100,000 blocks/epoch'},
    {label:'Block Time', value:s.block_time+'s', unit:'target'},
    {label:'Chain Tip', value:s.tip_hash.slice(0,10)+'…', unit:'sha3-256'},
  ];
  document.getElementById('stats').innerHTML = items.map(i=>`
    <div class="stat">
      <div class="stat-label">${i.label}</div>
      <div class="stat-value">${i.value}</div>
      <div class="stat-unit">${i.unit}</div>
    </div>`).join('');
}

function ramBadge(r) {
  const cls = {DDR2:'ddr2',DDR3:'ddr3',DDR4:'ddr4',DDR5:'ddr5'}[r]||'ddr4';
  return `<span class="badge ${cls}">${r}</span>`;
}

function renderLeaderboard(miners) {
  const sorted = Object.entries(miners).sort((a,b)=>b[1].blocks-a[1].blocks);
  document.getElementById('leaderboard').innerHTML = sorted.map(([id,s],i)=>{
    const boost = {DDR2:2.2,DDR3:1.6,DDR4:1.0,DDR5:0.85}[s.ram]||1.0;
    return `<div class="miner-card ${i===0?'winner':''}">
      <div class="miner-name">${ramBadge(s.ram)} &nbsp;${id}</div>
      <div class="miner-stats">
        <div class="ms"><div class="ms-label">Blocks</div><div class="ms-value">${s.blocks}</div></div>
        <div class="ms"><div class="ms-label">Reward</div><div class="ms-value">${s.reward.toFixed(1)} POLM</div></div>
        <div class="ms"><div class="ms-label">Avg latency</div><div class="ms-value">${s.avg_latency.toFixed(0)}ns</div></div>
        <div class="ms"><div class="ms-label">Boost</div><div class="ms-value">${boost}×</div></div>
      </div>
    </div>`;
  }).join('');
}

function renderBlocks(blocks) {
  const now = Math.floor(Date.now()/1000);
  if (!blocks.length) {
    document.getElementById('blocks').innerHTML = '<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--muted)">No blocks yet</td></tr>';
    return;
  }
  document.getElementById('blocks').innerHTML = blocks.map(b=>{
    const age = now - b.timestamp;
    const ageStr = age<60?age+'s':age<3600?Math.floor(age/60)+'m':Math.floor(age/3600)+'h';
    return `<tr>
      <td style="color:var(--green);font-family:var(--disp)">${b.height}</td>
      <td><span class="hash">${b.block_hash.slice(0,14)}…</span></td>
      <td><span class="hash-muted">${b.prev_hash.slice(0,10)}…</span></td>
      <td style="font-size:.72rem;color:var(--text)">${b.miner_id.slice(0,16)}…</td>
      <td>${ramBadge(b.ram_type)}</td>
      <td style="color:var(--amber)">${Number(b.score).toLocaleString('en',{maximumFractionDigits:0})}</td>
      <td style="color:var(--muted)">${Number(b.latency_ns).toFixed(0)}ns</td>
      <td style="color:var(--green)">${b.reward.toFixed(1)}</td>
      <td style="color:var(--muted)">${ageStr} ago</td>
    </tr>`;
  }).join('');
}

function search() {
  const q = document.getElementById('q').value.trim();
  if (!q) return;
  if (/^\d+$/.test(q)) { window.location.href = `/block/${q}`; return; }
  if (q.length === 64) { window.location.href = `/block/hash/${q}`; return; }
  alert('Enter a valid block height or 64-char hash');
}

load();
setInterval(load, 8000);
</script>
</body>
</html>
"""

def create_explorer(node_url: str = "http://localhost:6060", port: int = 5050):
    import urllib.request

    app = Flask("polm-explorer")

    def fetch(path):
        try:
            r = urllib.request.urlopen(f"{node_url}{path}", timeout=5)
            return json.loads(r.read())
        except:
            return None

    @app.route("/")
    def index():
        return render_template_string(EXPLORER_HTML)

    @app.route("/api/summary")
    def api_summary():
        data = fetch("/")
        if not data:
            return jsonify({"error": "node offline"}), 503
        return jsonify(data)

    @app.route("/api/blocks")
    def api_blocks():
        limit = request.args.get("limit", 20)
        data = fetch(f"/chain?limit={limit}")
        return jsonify(data or [])

    @app.route("/api/miners")
    def api_miners():
        data = fetch("/miners")
        return jsonify(data or {})

    @app.route("/block/<int:h>")
    def block_by_height(h):
        data = fetch(f"/block/{h}")
        if data:
            return jsonify(data)
        return jsonify({"error": "not found"}), 404

    @app.route("/block/hash/<h>")
    def block_by_hash(h):
        # search through recent blocks
        blocks = fetch("/chain?limit=200") or []
        for b in blocks:
            if b.get("block_hash") == h:
                return jsonify(b)
        return jsonify({"error": "not found"}), 404

    print(f"\n[Explorer] PoLM Explorer v3.1")
    print(f"[Explorer] Node: {node_url}")
    print(f"[Explorer] http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    import sys
    node = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:6060"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 5050
    create_explorer(node_url=node, port=port)
