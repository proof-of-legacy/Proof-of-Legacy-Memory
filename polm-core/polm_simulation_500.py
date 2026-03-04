import random

# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

BASELINE_LATENCY = 0.30
INITIAL_REWARD = 10
HALVING_INTERVAL = 50
TOTAL_BLOCKS = 500

NODE_CONFIG = {
    "Node-A (Modern)": 0.24,
    "Node-B (Legacy)": 0.40
}

# ==========================================================
# FUNÇÕES
# ==========================================================

def get_latency_factor(latency):
    factor = latency / BASELINE_LATENCY
    # 🔥 CALIBRAÇÃO v2.0 (Equilibrada)
    return min(max(factor, 0.90), 1.10)

def get_block_reward(height):
    halving_count = height // HALVING_INTERVAL
    base_reward = INITIAL_REWARD / (2 ** halving_count)
    return base_reward

# ==========================================================
# SIMULAÇÃO ESTATÍSTICA
# ==========================================================

ledger = {}
win_count = {}
total_emission = 0

for node in NODE_CONFIG:
    ledger[node] = 0
    win_count[node] = 0

for height in range(1, TOTAL_BLOCKS + 1):

    weights = []
    nodes = []

    for node, latency in NODE_CONFIG.items():
        latency_factor = get_latency_factor(latency)
        weights.append(latency_factor)
        nodes.append(node)

    winner = random.choices(nodes, weights=weights, k=1)[0]

    reward = get_block_reward(height)

    ledger[winner] += reward
    win_count[winner] += 1
    total_emission += reward

# ==========================================================
# RESULTADOS
# ==========================================================

print("\n=== PoLM v2.0 Balanced Simulation Results ===")
print("Total Blocks:", TOTAL_BLOCKS)
print("Total Emission:", round(total_emission, 4))

print("\n--- Wins ---")
for node in win_count:
    percent = (win_count[node] / TOTAL_BLOCKS) * 100
    print(node, ":", win_count[node],
          f"blocks ({percent:.2f}%)")

print("\n--- Ledger ---")
for node in ledger:
    percent = (ledger[node] / total_emission) * 100
    print(node, ":", round(ledger[node], 4),
          f"({percent:.2f}% of supply)")
