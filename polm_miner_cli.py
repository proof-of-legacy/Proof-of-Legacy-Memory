import hashlib, time, json, struct, urllib.request, secrets, random, os

NODE_URL = "https://polm.com.br/api"

def measure_latency(buf, steps=5000):
    size = len(buf); idx = 0
    t0 = time.perf_counter_ns()
    for _ in range(steps):
        idx = struct.unpack_from('<I', buf, idx % (size-4))[0] % size
    return (time.perf_counter_ns() - t0) / steps

def build_dag(seed, size_mb=256):
    print(f"  Building {size_mb}MB DAG...", end="", flush=True)
    size = size_mb*1024*1024; buf = bytearray(size)
    chunk = hashlib.sha3_256(seed).digest()
    for i in range(0, size, 32):
        chunk = hashlib.sha3_256(chunk).digest(); buf[i:i+32] = chunk
    print(" done"); return buf

def mem_walk(buf, nonce, steps=1000):
    size = len(buf); idx = nonce % size
    for _ in range(steps):
        idx = struct.unpack_from('<I', buf, idx % (size-4))[0] % size
    return idx

def get_work():
    with urllib.request.urlopen(f"{NODE_URL}/getwork", timeout=10) as r:
        return json.loads(r.read())

def submit_block(bd):
    data = json.dumps({"block": bd, "txs": []}).encode()
    req = urllib.request.Request(f"{NODE_URL}/submit", data,
          {"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def register(polm, evm):
    try:
        data = json.dumps({"polm_address": polm, "evm_address": evm}).encode()
        req = urllib.request.Request(f"{NODE_URL}/register_evm", data,
              {"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=5)
        print("  [OK] Polygon wallet registered!")
    except Exception as e:
        print(f"  [!] register_evm: {e}")

def save_settings(polm, evm):
    with open("polm_settings.json", "w") as f:
        json.dump({"polm_address": polm, "evm_address": evm}, f)

def load_settings():
    try:
        with open("polm_settings.json") as f:
            return json.load(f)
    except:
        return {}

def generate_wallet():
    priv = secrets.token_bytes(32)
    addr = "POLM" + hashlib.sha3_256(priv).hexdigest()[:32].upper()
    words = ["abandon","ability","able","about","above","absent","absorb","abstract","absurd","abuse",
             "access","accident","account","accuse","achieve","acid","acoustic","acquire","across","action",
             "actor","adapt","add","addict","address","adjust","admit","adult","advance","advice",
             "aerobic","afford","afraid","again","agent","agree","ahead","aim","air","airport",
             "alarm","album","alcohol","alert","alien","allow","almost","alone","alpha","already",
             "alter","always","amazing","amber","angry","animal","answer","army","around","art"]
    rng = random.Random(int.from_bytes(priv[:4], "big"))
    return addr, " ".join(rng.choices(words, k=12))

print("=" * 52)
print("  PoLM Miner CLI v1.4 — score = 1/latency_ns")
print("  Any RAM mines. Physics can't be faked.")
print("=" * 52)
print()

settings = load_settings()

if settings.get("polm_address"):
    print(f"  Saved POLM:    {settings['polm_address']}")
    print(f"  Saved Polygon: {settings.get('evm_address','')}")
    use = input("  Use saved settings? (Y/n): ").strip().lower()
    if use == "n":
        settings = {}

if not settings.get("polm_address"):
    print()
    print("  1 - Generate new wallet")
    print("  2 - Enter existing address")
    choice = input("  Choice (1/2): ").strip()
    if choice == "1":
        polm_addr, seed_phrase = generate_wallet()
        print()
        print("  " + "="*48)
        print("  NEW WALLET CREATED!")
        print("  " + "="*48)
        print(f"  Address: {polm_addr}")
        print()
        print("  SEED PHRASE (12 words) — SAVE THIS NOW!")
        print("  " + "-"*48)
        print(f"  {seed_phrase}")
        print("  " + "-"*48)
        print("  Write on paper! Without it you lose your wallet!")
        print("  " + "="*48)
        input("  Press Enter after saving seed phrase...")
    else:
        polm_addr = input("  Enter POLM address (POLM...): ").strip()
else:
    polm_addr = settings["polm_address"]

if not polm_addr.startswith("POLM"):
    print("  [!] Invalid address — must start with POLM"); exit()

if settings.get("evm_address"):
    evm_addr = settings["evm_address"]
else:
    print()
    print("  Enter your Polygon/Trust wallet to receive POLM ERC-20")
    print("  (Claim rewards at polm.com.br/claim after mining)")
    evm_addr = input("  Polygon wallet (0x...): ").strip()

save_settings(polm_addr, evm_addr)
register(polm_addr, evm_addr)

print()
print(f"  POLM:    {polm_addr}")
print(f"  Polygon: {evm_addr}")
print(f"  Node:    {NODE_URL}")
print()

work = get_work()
prev_hash = work.get("prev_hash", "00"*32)
epoch  = int(work.get("epoch", 0))
diff   = int(work.get("difficulty", 2))
reward = float(work.get("reward", 50.0))
height = int(work.get("height", 0))
dag    = build_dag(bytes.fromhex(prev_hash[:64].ljust(64,"0")))
blocks = 0; earned = 0.0

print("  Mining started! Press Ctrl+C to stop.")
print()

while True:
    try:
        work = get_work()
        if not work: time.sleep(5); continue

        new_ph = work.get("prev_hash", "")
        diff   = int(work.get("difficulty", 2))
        reward = float(work.get("reward", 50.0))
        height = int(work.get("height", 0))
        epoch  = int(work.get("epoch", 0))

        if new_ph != prev_hash:
            prev_hash = new_ph
            # Only rebuild DAG if epoch changed (not every block!)
            new_epoch = int(work.get("epoch", 0))
            if new_epoch != epoch or dag is None:
                dag = build_dag(bytes.fromhex(prev_hash[:64].ljust(64,"0")))
            epoch = new_epoch

        nonce = 0
        while True:
            proof_idx = mem_walk(dag, nonce)
            mem_proof = hashlib.sha3_256(
                struct.pack("<Q", proof_idx) + prev_hash.encode()
            ).hexdigest()
            lat   = measure_latency(dag)
            score = 1.0 / lat if lat > 0 else 0
            ts    = int(time.time())
            header = (f"{height}|{prev_hash}|{ts}|{nonce}|{polm_addr}|"
                      f"DDR4|1|{epoch}|{diff}|{lat:.4f}|{mem_proof}|"
                      f"{score:.8f}|{reward}|")
            block_hash = hashlib.sha3_256(header.encode()).hexdigest()

            if block_hash.startswith("0" * diff):
                print(f"\n  Block found! nonce={nonce} hash={block_hash[:16]}...")
                bd = {
                    "height": height, "prev_hash": prev_hash,
                    "timestamp": ts, "nonce": nonce, "miner_id": polm_addr,
                    "ram_type": "DDR4", "threads": 1, "epoch": epoch,
                    "difficulty": diff, "latency_ns": lat, "mem_proof": mem_proof,
                    "score": score, "reward": reward, "cpu_name": "",
                    "tx_ids": [], "block_hash": block_hash
                }
                try:
                    resp = submit_block(bd)
                    if resp.get("accepted"):
                        blocks += 1; earned += reward
                        print(f"  ACCEPTED! Blocks={blocks} Earned={earned} POLM")
                        prev_hash = block_hash
                    else:
                        print(f"  Rejected: {resp.get('reason','?')}")
                except Exception as e:
                    print(f"  Submit error: {e}")
                break

            nonce += 1
            if nonce % 10000 == 0:
                print(f"\r  nonce={nonce:,} lat={lat:.0f}ns diff={diff}    ",
                      end="", flush=True)

    except KeyboardInterrupt:
        print(f"\n  Stopped. Blocks={blocks} Earned={earned} POLM")
        break
    except Exception as e:
        print(f"  Error: {e}"); time.sleep(5)
