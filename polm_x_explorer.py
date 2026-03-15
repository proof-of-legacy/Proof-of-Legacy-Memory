"""
PoLM-X v2 — Explorer
Web-based blockchain explorer with retro-terminal aesthetic.
"""

from flask import Flask, render_template_string, jsonify, request
from polm_x_core import (
    PoLMChain, POLM_VERSION, COIN_SYMBOL, MAX_SUPPLY,
    block_reward, get_epoch, get_min_ram_mb, get_dag_size_mb,
    LEGACY_BOOST, RAMType,
)
import time, json
from dataclasses import asdict

EXPLORER_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PoLM-X Explorer</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
<style>
:root {
  --bg:       #080c10;
  --surface:  #0d1520;
  --border:   #1a3050;
  --accent:   #00e5ff;
  --accent2:  #00ff88;
  --accent3:  #ff6b35;
  --warn:     #ffb300;
  --text:     #c8dff0;
  --muted:    #4a6a8a;
  --font-mono: 'Share Tech Mono', monospace;
  --font-disp: 'Orbitron', monospace;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 14px; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-mono);
  min-height: 100vh;
  background-image:
    radial-gradient(ellipse 80% 50% at 50% -10%, rgba(0,229,255,0.07) 0%, transparent 70%),
    repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(0,229,255,0.02) 40px),
    repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(0,229,255,0.02) 40px);
}

/* ── HEADER ── */
header {
  border-bottom: 1px solid var(--border);
  padding: 18px 32px;
  display: flex; align-items: center; gap: 24px;
  background: rgba(13,21,32,0.95);
  position: sticky; top: 0; z-index: 100;
  backdrop-filter: blur(12px);
}
.logo {
  font-family: var(--font-disp);
  font-size: 1.5rem;
  font-weight: 900;
  letter-spacing: 0.12em;
  color: var(--accent);
  text-shadow: 0 0 20px rgba(0,229,255,0.5);
}
.logo span { color: var(--accent2); }
.tagline { font-size: 0.75rem; color: var(--muted); letter-spacing: 0.1em; }
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent2);
  box-shadow: 0 0 8px var(--accent2);
  animation: pulse 2s infinite;
  margin-left: auto;
}
@keyframes pulse {
  0%,100% { opacity: 1; } 50% { opacity: 0.3; }
}

/* ── LAYOUT ── */
main { max-width: 1400px; margin: 0 auto; padding: 28px 24px; }

/* ── STATS GRID ── */
.stats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
  margin-bottom: 32px;
}
.stat-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 16px 20px;
  position: relative;
  overflow: hidden;
  transition: border-color 0.2s;
}
.stat-card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  opacity: 0.5;
}
.stat-card:hover { border-color: var(--accent); }
.stat-label { font-size: 0.7rem; color: var(--muted); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 8px; }
.stat-value { font-family: var(--font-disp); font-size: 1.4rem; font-weight: 700; color: var(--accent); }
.stat-unit  { font-size: 0.7rem; color: var(--muted); margin-top: 2px; }

/* ── SECTION TITLE ── */
.section-title {
  font-family: var(--font-disp);
  font-size: 0.8rem;
  letter-spacing: 0.2em;
  color: var(--muted);
  text-transform: uppercase;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

/* ── BLOCK TABLE ── */
.block-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 32px;
  font-size: 0.82rem;
}
.block-table th {
  text-align: left;
  padding: 10px 14px;
  color: var(--muted);
  font-size: 0.65rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  border-bottom: 1px solid var(--border);
}
.block-table td {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(26,48,80,0.5);
  vertical-align: middle;
}
.block-table tr:hover td { background: rgba(0,229,255,0.03); cursor: pointer; }
.hash { color: var(--accent); font-size: 0.78rem; }
.hash-muted { color: var(--muted); font-size: 0.72rem; }
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 3px;
  font-size: 0.68rem;
  letter-spacing: 0.06em;
  font-weight: 700;
}
.badge-ddr2 { background: rgba(255,107,53,0.15); color: var(--accent3); border: 1px solid rgba(255,107,53,0.3); }
.badge-ddr3 { background: rgba(255,179,0,0.12); color: var(--warn); border: 1px solid rgba(255,179,0,0.3); }
.badge-ddr4 { background: rgba(0,229,255,0.1); color: var(--accent); border: 1px solid rgba(0,229,255,0.3); }
.badge-ddr5 { background: rgba(0,255,136,0.1); color: var(--accent2); border: 1px solid rgba(0,255,136,0.3); }

/* ── EPOCH INFO ── */
.epoch-bar {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 20px 24px;
  margin-bottom: 32px;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 1fr;
  gap: 20px;
}
.epoch-item label { font-size: 0.65rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; }
.epoch-item .val { font-family: var(--font-disp); color: var(--accent2); font-size: 1.1rem; margin-top: 4px; }

/* ── LEGACY BOOST TABLE ── */
.boost-table {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 32px;
}
.boost-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 16px;
  text-align: center;
}
.boost-type { font-family: var(--font-disp); font-size: 1.2rem; font-weight: 700; margin-bottom: 6px; }
.boost-mult { font-size: 1.6rem; font-weight: 700; }
.boost-card.ddr2 .boost-type, .boost-card.ddr2 .boost-mult { color: var(--accent3); }
.boost-card.ddr3 .boost-type, .boost-card.ddr3 .boost-mult { color: var(--warn); }
.boost-card.ddr4 .boost-type, .boost-card.ddr4 .boost-mult { color: var(--accent); }
.boost-card.ddr5 .boost-type, .boost-card.ddr5 .boost-mult { color: var(--accent2); }
.boost-label { font-size: 0.65rem; color: var(--muted); margin-top: 4px; }

/* ── SEARCH ── */
.search-bar {
  display: flex; gap: 8px;
  margin-bottom: 20px;
}
.search-bar input {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 10px 14px;
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 0.85rem;
  outline: none;
}
.search-bar input:focus { border-color: var(--accent); }
.search-bar button {
  background: rgba(0,229,255,0.1);
  border: 1px solid var(--accent);
  color: var(--accent);
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-family: var(--font-disp);
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  transition: background 0.2s;
}
.search-bar button:hover { background: rgba(0,229,255,0.2); }

/* ── FOOTER ── */
footer {
  border-top: 1px solid var(--border);
  padding: 20px 32px;
  text-align: center;
  color: var(--muted);
  font-size: 0.72rem;
  letter-spacing: 0.08em;
}

/* ── SCANLINE OVERLAY ── */
body::after {
  content: '';
  pointer-events: none;
  position: fixed; inset: 0;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px
  );
  z-index: 9999;
}

@media (max-width: 768px) {
  .boost-table { grid-template-columns: repeat(2,1fr); }
  .epoch-bar { grid-template-columns: repeat(2,1fr); }
  header { padding: 14px 16px; }
  main { padding: 16px; }
}
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">PoLM<span>-X</span> Explorer</div>
    <div class="tagline">Proof of Legacy Memory · Memory-Hard + Latency-Hard</div>
  </div>
  <div class="status-dot" title="Node online"></div>
</header>

<main>

  <!-- SEARCH -->
  <div class="search-bar">
    <input id="searchInput" placeholder="Search block height, hash, or address…" onkeydown="if(event.key==='Enter')doSearch()">
    <button onclick="doSearch()">SEARCH</button>
  </div>

  <!-- STATS -->
  <div class="stats" id="statsGrid">
    <!-- filled by JS -->
  </div>

  <!-- EPOCH INFO -->
  <p class="section-title">Current Epoch</p>
  <div class="epoch-bar" id="epochBar">
    <!-- filled by JS -->
  </div>

  <!-- LEGACY BOOSTS -->
  <p class="section-title">Legacy Boost Multipliers</p>
  <div class="boost-table">
    <div class="boost-card ddr2">
      <div class="boost-type">DDR2</div>
      <div class="boost-mult">2.20×</div>
      <div class="boost-label">Maximum Legacy Bonus</div>
    </div>
    <div class="boost-card ddr3">
      <div class="boost-type">DDR3</div>
      <div class="boost-mult">1.60×</div>
      <div class="boost-label">Strong Legacy Bonus</div>
    </div>
    <div class="boost-card ddr4">
      <div class="boost-type">DDR4</div>
      <div class="boost-mult">1.00×</div>
      <div class="boost-label">Baseline</div>
    </div>
    <div class="boost-card ddr5">
      <div class="boost-type">DDR5</div>
      <div class="boost-mult">0.85×</div>
      <div class="boost-label">Modern Penalty</div>
    </div>
  </div>

  <!-- BLOCKS -->
  <p class="section-title">Latest Blocks</p>
  <table class="block-table">
    <thead>
      <tr>
        <th>#</th>
        <th>Hash</th>
        <th>Prev Hash</th>
        <th>Miner</th>
        <th>RAM</th>
        <th>Score</th>
        <th>Latency</th>
        <th>Reward</th>
        <th>Time</th>
      </tr>
    </thead>
    <tbody id="blocksBody">
      <!-- filled by JS -->
    </tbody>
  </table>

</main>

<footer>
  PoLM-X v{{ version }} &nbsp;·&nbsp; Supply max: {{ max_supply | int | format_number }} {{ symbol }}
  &nbsp;·&nbsp; Experimental Testnet
</footer>

<script>
async function loadChain() {
  try {
    const [summary, blocks] = await Promise.all([
      fetch('/api/summary').then(r=>r.json()),
      fetch('/api/blocks?limit=20').then(r=>r.json()),
    ]);
    renderStats(summary);
    renderEpoch(summary);
    renderBlocks(blocks);
  } catch(e) { console.error(e); }
}

function renderStats(s) {
  const items = [
    { label: 'Block Height',   value: s.height.toLocaleString(),          unit: 'blocks' },
    { label: 'Difficulty',     value: s.difficulty,                        unit: 'leading zeros' },
    { label: 'Next Reward',    value: s.next_reward.toFixed(4),            unit: 'POLM' },
    { label: 'Total Supply',   value: Number(s.total_supply).toLocaleString('en',{maximumFractionDigits:2}), unit: `/ ${(32000000).toLocaleString()} POLM` },
    { label: 'Epoch',          value: s.epoch,                             unit: `${(100000).toLocaleString()} blocks/epoch` },
    { label: 'Min RAM',        value: (s.min_ram_mb/1024).toFixed(0),      unit: 'GB required' },
    { label: 'DAG Size',       value: (s.dag_size_mb/1024).toFixed(2),     unit: 'GB' },
    { label: 'Chain Tip',      value: s.tip_hash.slice(0,10)+'…',          unit: 'sha3-256' },
  ];
  document.getElementById('statsGrid').innerHTML = items.map(i=>
    `<div class="stat-card">
      <div class="stat-label">${i.label}</div>
      <div class="stat-value">${i.value}</div>
      <div class="stat-unit">${i.unit}</div>
    </div>`
  ).join('');
}

function renderEpoch(s) {
  document.getElementById('epochBar').innerHTML = `
    <div class="epoch-item"><label>Current Epoch</label><div class="val">${s.epoch}</div></div>
    <div class="epoch-item"><label>Min RAM</label><div class="val">${(s.min_ram_mb/1024).toFixed(0)} GB</div></div>
    <div class="epoch-item"><label>DAG Size</label><div class="val">${(s.dag_size_mb/1024).toFixed(2)} GB</div></div>
    <div class="epoch-item"><label>Next Epoch</label><div class="val">Block ${((s.epoch+1)*100000).toLocaleString()}</div></div>
  `;
}

function ramBadge(ram) {
  const cls = { DDR2:'ddr2', DDR3:'ddr3', DDR4:'ddr4', DDR5:'ddr5' }[ram] || 'ddr4';
  return `<span class="badge badge-${cls}">${ram}</span>`;
}

function renderBlocks(blocks) {
  if (!blocks.length) { document.getElementById('blocksBody').innerHTML = '<tr><td colspan="9" style="color:var(--muted);text-align:center;padding:32px">No blocks yet</td></tr>'; return; }
  document.getElementById('blocksBody').innerHTML = blocks.map(b => {
    const age = Math.floor(Date.now()/1000) - b.timestamp;
    const ageStr = age < 60 ? age+'s ago' : age < 3600 ? Math.floor(age/60)+'m ago' : Math.floor(age/3600)+'h ago';
    return `<tr>
      <td style="color:var(--accent2);font-family:var(--font-disp)">${b.height}</td>
      <td><span class="hash">${b.block_hash.slice(0,14)}…</span></td>
      <td><span class="hash-muted">${b.prev_hash.slice(0,10)}…</span></td>
      <td style="color:var(--text);font-size:0.75rem">${b.miner_id.slice(0,12)}…</td>
      <td>${ramBadge(b.ram_type)}</td>
      <td style="color:var(--warn)">${Number(b.score).toFixed(0)}</td>
      <td style="color:var(--muted)">${Number(b.latency_proof).toFixed(1)}ns</td>
      <td style="color:var(--accent2)">${b.transactions.filter(t=>t.sender==='COINBASE').reduce((s,t)=>s+t.amount,0).toFixed(4)}</td>
      <td style="color:var(--muted);font-size:0.72rem">${ageStr}</td>
    </tr>`;
  }).join('');
}

async function doSearch() {
  const q = document.getElementById('searchInput').value.trim();
  if (!q) return;
  // try height
  if (/^\\d+$/.test(q)) {
    window.location.href = `/block/${q}`;
    return;
  }
  // try hash
  if (q.length === 64) {
    window.location.href = `/block/hash/${q}`;
    return;
  }
  alert('Enter a valid block height or 64-char hash');
}

loadChain();
setInterval(loadChain, 10000);
</script>
</body>
</html>
"""

def create_explorer(chain: PoLMChain, port: int = 5050):
    app = Flask("polmx-explorer")

    @app.route("/")
    def index():
        return render_template_string(
            EXPLORER_HTML,
            version=POLM_VERSION,
            max_supply=MAX_SUPPLY,
            symbol=COIN_SYMBOL,
        )

    @app.route("/api/summary")
    def api_summary():
        return jsonify(chain.summary())

    @app.route("/api/blocks")
    def api_blocks():
        limit  = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
        blocks = chain.chain[::-1][offset:offset+limit]
        return jsonify([b.to_dict() for b in blocks])

    @app.route("/block/<int:height>")
    def block_detail(height):
        if 0 <= height <= chain.height:
            return jsonify(chain.chain[height].to_dict())
        return jsonify({"error": "not found"}), 404

    @app.route("/block/hash/<h>")
    def block_by_hash(h):
        for blk in chain.chain:
            if blk.block_hash == h:
                return jsonify(blk.to_dict())
        return jsonify({"error": "not found"}), 404

    print(f"[Explorer] http://localhost:{port}")
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    chain = PoLMChain(chain_file="polmx_chain.json", testnet=True)
    create_explorer(chain, port=5050)
