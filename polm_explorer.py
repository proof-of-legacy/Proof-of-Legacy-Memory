"""
polm_explorer.py — PoLM Block Explorer
=========================================
Interface web para explorar a blockchain PoLM.

Rotas:
  GET /                    — página inicial com estatísticas
  GET /block/<height>      — detalhes de um bloco
  GET /tx/<txid>           — detalhes de uma transação
  GET /address/<addr>      — saldo e histórico de um endereço
  GET /api/stats           — estatísticas em JSON
  GET /api/chain           — últimos blocos em JSON
  GET /api/mempool         — transações pendentes

Uso:
    python3 polm_explorer.py
    Abra: http://localhost:5000
"""

import json
import os
import sys
import time
from typing import Optional

try:
    from flask import Flask, jsonify, render_template_string, abort
except ImportError:
    print("Flask não instalado. Execute: pip install flask")
    sys.exit(1)

from polm_core import COIN, MAX_SUPPLY_COINS, CHAIN_FILE, UTXO_FILE
from polm_chain import Blockchain

app   = Flask(__name__)
chain = Blockchain()

# ═══════════════════════════════════════════════════════════
# TEMPLATE HTML
# ═══════════════════════════════════════════════════════════

BASE_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PoLM Explorer — Proof of Legacy Memory</title>
<style>
  :root {
    --bg:     #0d0f14;
    --surface:#161b26;
    --border: #2a3040;
    --accent: #00d4aa;
    --accent2:#ff6b35;
    --text:   #e2e8f0;
    --muted:  #8896a8;
    --green:  #22c55e;
    --red:    #ef4444;
    --font:   'JetBrains Mono', 'Courier New', monospace;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
    font-size: 13px;
    line-height: 1.6;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }

  header {
    border-bottom: 1px solid var(--border);
    padding: 16px 32px;
    display: flex;
    align-items: center;
    gap: 24px;
  }
  .logo {
    font-size: 20px;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: 2px;
  }
  .logo span { color: var(--accent2); }
  nav a {
    color: var(--muted);
    margin-right: 20px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  nav a:hover { color: var(--text); }

  .container { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 36px;
  }
  .stat-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px;
  }
  .stat-label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
  .stat-value { font-size: 22px; font-weight: 700; color: var(--accent); margin-top: 6px; }
  .stat-sub   { color: var(--muted); font-size: 11px; margin-top: 4px; }

  .section-title {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--muted);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
    margin-bottom: 16px;
  }

  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
  }
  td {
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    font-size: 12px;
  }
  tr:hover td { background: var(--surface); }

  .hash {
    font-family: var(--font);
    font-size: 11px;
    color: var(--muted);
  }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .badge-ddr2 { background: #7c3aed22; color: #a78bfa; border: 1px solid #7c3aed44; }
  .badge-ddr3 { background: #065f4622; color: #6ee7b7; border: 1px solid #065f4644; }
  .badge-ddr4 { background: #1e3a5f22; color: #60a5fa; border: 1px solid #1e3a5f44; }
  .badge-ddr5 { background: #7c1d1322; color: #fca5a5; border: 1px solid #7c1d1344; }

  .supply-bar-wrap {
    background: var(--border);
    border-radius: 4px;
    height: 6px;
    overflow: hidden;
    margin-top: 8px;
  }
  .supply-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
    border-radius: 4px;
    transition: width 1s ease;
  }

  .block-detail { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 24px; }
  .detail-row { display: flex; padding: 10px 0; border-bottom: 1px solid var(--border); gap: 16px; }
  .detail-key { width: 160px; color: var(--muted); font-size: 11px; text-transform: uppercase; flex-shrink: 0; }
  .detail-val { color: var(--text); word-break: break-all; }

  .polm-amount { color: var(--green); font-weight: 700; }
  .fee-amount  { color: var(--accent2); }

  footer {
    border-top: 1px solid var(--border);
    padding: 20px 32px;
    color: var(--muted);
    font-size: 11px;
    text-align: center;
    margin-top: 60px;
  }
</style>
</head>
<body>
<header>
  <div class="logo">Po<span>LM</span></div>
  <nav>
    <a href="/">Dashboard</a>
    <a href="/blocks">Blocos</a>
    <a href="/api/stats">API</a>
  </nav>
</header>
{% block body %}{% endblock %}
<footer>PoLM — Proof of Legacy Memory &nbsp;|&nbsp; Supply máximo: 32.000.000 PoLM &nbsp;|&nbsp; DDR2 vive.</footer>
</body></html>"""

INDEX_HTML = BASE_HTML.replace("{% block body %}{% endblock %}", """
<div class="container">
  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-label">Altura</div>
      <div class="stat-value">{{ stats.height }}</div>
      <div class="stat-sub">blocos confirmados</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Supply</div>
      <div class="stat-value">{{ "%.0f"|format(stats.supply) }}</div>
      <div class="stat-sub">de 32.000.000 PoLM ({{ "%.3f"|format(stats.supply_pct) }}%)</div>
      <div class="supply-bar-wrap"><div class="supply-bar" style="width:{{ stats.supply_pct }}%"></div></div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Dificuldade</div>
      <div class="stat-value">{{ stats.difficulty }}</div>
      <div class="stat-sub">bits de PoW</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Último hash</div>
      <div class="stat-value" style="font-size:13px">{{ stats.tip_hash[:14] }}…</div>
      <div class="stat-sub">bloco mais recente</div>
    </div>
  </div>

  <div class="section-title">Últimos blocos</div>
  <table>
    <thead>
      <tr>
        <th>Altura</th>
        <th>Hash</th>
        <th>Minerador</th>
        <th>RAM</th>
        <th>Score</th>
        <th>TXs</th>
        <th>Recompensa</th>
        <th>Tempo</th>
      </tr>
    </thead>
    <tbody>
    {% for b in blocks %}
      <tr>
        <td><a href="/block/{{ b.height }}">{{ b.height }}</a></td>
        <td><span class="hash"><a href="/block/{{ b.height }}">{{ b.hash[:20] }}…</a></span></td>
        <td><span class="hash">{{ b.miner[:20] }}…</span></td>
        <td>
          {% set ram = b.get('ram_type', b.get('ram', 'AUTO')) %}
          <span class="badge badge-{{ ram.lower() }}">{{ ram }}</span>
        </td>
        <td>{{ "%.2f"|format(b.get('ram_score', 0)) }}</td>
        <td>{{ b.transactions|length }}</td>
        <td class="polm-amount">{{ "%.4f"|format(b.transactions[0].outputs[0].value / 100000000) }}</td>
        <td class="hash">{{ b.timestamp | ts_ago }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
""")

BLOCK_HTML = BASE_HTML.replace("{% block body %}{% endblock %}", """
<div class="container">
  <div class="section-title">Bloco #{{ block.height }}</div>
  <div class="block-detail">
    <div class="detail-row"><div class="detail-key">Hash</div><div class="detail-val hash">{{ block.hash }}</div></div>
    <div class="detail-row"><div class="detail-key">Altura</div><div class="detail-val">{{ block.height }}</div></div>
    <div class="detail-row"><div class="detail-key">Anterior</div><div class="detail-val hash"><a href="/block/{{ block.height - 1 }}">{{ block.prev_hash[:32] }}…</a></div></div>
    <div class="detail-row"><div class="detail-key">Merkle Root</div><div class="detail-val hash">{{ block.merkle_root }}</div></div>
    <div class="detail-row"><div class="detail-key">Timestamp</div><div class="detail-val">{{ block.timestamp | ts_fmt }}</div></div>
    <div class="detail-row"><div class="detail-key">Dificuldade</div><div class="detail-val">{{ block.difficulty }} bits</div></div>
    <div class="detail-row"><div class="detail-key">Nonce</div><div class="detail-val">{{ block.nonce }}</div></div>
    <div class="detail-row"><div class="detail-key">Minerador</div><div class="detail-val hash">{{ block.miner }}</div></div>
    <div class="detail-row"><div class="detail-key">RAM</div><div class="detail-val">{{ block.get('ram_type', block.get('ram', '—')) }} | score={{ "%.4f"|format(block.get('ram_score', 0)) }} | latência={{ "%.4f"|format(block.get('ram_latency', 0)) }}s</div></div>
    <div class="detail-row"><div class="detail-key">Transações</div><div class="detail-val">{{ block.transactions|length }}</div></div>
  </div>

  <br>
  <div class="section-title">Transações</div>
  <table>
    <thead><tr><th>TXID</th><th>Tipo</th><th>Outputs</th><th>Total</th></tr></thead>
    <tbody>
    {% for tx in block.transactions %}
    <tr>
      <td><span class="hash"><a href="/tx/{{ tx.txid }}">{{ tx.txid[:24] }}…</a></span></td>
      <td>{% if tx.inputs[0].txid == '0'*64 %}<span class="badge badge-ddr3">COINBASE</span>{% else %}TX{% endif %}</td>
      <td>{{ tx.outputs|length }}</td>
      <td class="polm-amount">{{ "%.8f"|format(tx.outputs|sum(attribute='value') / 100000000) }} PoLM</td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
""")

# ═══════════════════════════════════════════════════════════
# TEMPLATE FILTERS
# ═══════════════════════════════════════════════════════════

@app.template_filter("ts_ago")
def ts_ago(ts):
    delta = int(time.time() - ts)
    if delta < 60:    return f"{delta}s atrás"
    if delta < 3600:  return f"{delta//60}m atrás"
    if delta < 86400: return f"{delta//3600}h atrás"
    return f"{delta//86400}d atrás"

@app.template_filter("ts_fmt")
def ts_fmt(ts):
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts))

# ═══════════════════════════════════════════════════════════
# ROTAS
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    tip     = chain.tip or {}
    supply  = chain.total_supply() / COIN
    blocks  = list(reversed(chain.get_recent_blocks(20)))

    stats = {
        "height":     chain.height,
        "supply":     supply,
        "supply_pct": supply / MAX_SUPPLY_COINS * 100,
        "difficulty": tip.get("difficulty", 0),
        "tip_hash":   tip.get("hash", "—"),
    }
    return render_template_string(INDEX_HTML, stats=stats, blocks=blocks)


@app.route("/block/<int:height>")
def block_detail(height: int):
    block = chain.get_block(height)
    if not block:
        abort(404)
    return render_template_string(BLOCK_HTML, block=block)


@app.route("/address/<addr>")
def address_detail(addr: str):
    utxos   = chain.utxo.get_by_address(addr, chain.height)
    balance = sum(u["value"] for u in utxos) / COIN
    # Estatísticas de mineradores
    miners = {}
    for b in bc[-500:]:
        m = b.get('miner', '')
        r = b.get('ram_type', b.get('ram_proof', {}) if isinstance(b.get('ram_proof'), dict) else 'AUTO')
        if isinstance(r, dict):
            r = r.get('ram_type', 'AUTO')
        s = b.get('ram_score', 0)
        if m not in miners:
            miners[m] = {'blocks': 0, 'ram_type': r, 'total_score': 0}
        miners[m]['blocks'] += 1
        miners[m]['total_score'] += s

    miner_stats = sorted([
        {'miner': m[:20], 'blocks': v['blocks'], 'ram_type': v['ram_type'],
         'avg_score': round(v['total_score'] / max(v['blocks'], 1), 2)}
        for m, v in miners.items()
    ], key=lambda x: -x['blocks'])

    return jsonify({
        "address": addr,
        "balance": balance,
        "utxos":   utxos,
    })


@app.route("/tx/<txid>")
def tx_detail(txid: str):
    for block in reversed(chain.get_recent_blocks(1000)):
        for tx in block.get("transactions", []):
            if tx.get("txid") == txid:
                return jsonify({**tx, "confirmed_in_block": block["height"]})
    abort(404)


@app.route("/api/stats")
def api_stats():
    tip    = chain.tip or {}
    supply = chain.total_supply() / COIN
    return jsonify({
        "height":       chain.height,
        "tip_hash":     tip.get("hash", ""),
        "difficulty":   tip.get("difficulty", 0),
        "supply_polm":  round(supply, 8),
        "supply_pct":   round(supply / MAX_SUPPLY_COINS * 100, 6),
        "max_supply":   MAX_SUPPLY_COINS,
        "timestamp":    time.time(),
    })


@app.route("/api/chain")
def api_chain():
    blocks = chain.get_recent_blocks(50)
    return jsonify(blocks)


@app.route("/api/block/<int:height>")
def api_block(height: int):
    block = chain.get_block(height)
    if not block:
        abort(404)
    return jsonify(block)


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    chain.initialize()
    print("\n  PoLM Explorer — http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False)
