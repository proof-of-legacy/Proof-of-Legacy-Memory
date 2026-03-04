import json

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def calculate_score():

    try:
        with open("proofs.json", "r") as f:
            proofs = json.load(f)
    except FileNotFoundError:
        print("No proofs found.")
        return

    total_proofs = len(proofs)

    if total_proofs == 0:
        print("No proofs recorded yet.")
        return

    avg_latency = sum(p["latency"] for p in proofs) / total_proofs

    # --- Latency Weighted Model ---
    latency_weight = clamp(avg_latency * 12, 1.0, 4.0)
    base_rate = total_proofs / avg_latency

    score = base_rate * latency_weight

    print("\n=== NODE SCORE v0.5 ===")
    print("Total Proofs:", total_proofs)
    print("Average Latency:", round(avg_latency, 4))
    print("Latency Weight:", round(latency_weight, 3))
    print("Base Rate:", round(base_rate, 2))
    print("Final Score:", round(score, 2))

if __name__ == "__main__":
    calculate_score()
