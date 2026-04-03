import hashlib, time, json, struct, urllib.request, secrets, random, os

NODE_URL   = "https://polm.com.br/api"
MINER_URL  = "https://raw.githubusercontent.com/proof-of-legacy/Proof-of-Legacy-Memory/main/polm_miner_cli.py"
VERSION    = "1.5.2"

def check_update():
    """Auto-update: checks GitHub for newer version and restarts if found"""
    try:
        import urllib.request, os, sys
        r = urllib.request.urlopen(MINER_URL + "?nocache=" + str(int(time.time())), timeout=5)
        new_code = r.read().decode()
        # Check version in remote file
        for line in new_code.splitlines():
            if line.strip().startswith("VERSION"):
                remote_ver = line.split("=")[1].strip().strip('"').strip("'")
                if remote_ver != VERSION:
                    print(f"  [Update] New version {remote_ver} found! Updating...")
                    this_file = os.path.abspath(__file__)
                    open(this_file, "w", encoding="utf-8").write(new_code)
                    print(f"  [Update] Updated! Restarting...")
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                else:
                    print(f"  [OK] Version {VERSION} is up to date.")
                return
    except Exception as e:
        print(f"  [Update] Could not check for updates: {e}")

def detect_ram():
    import platform, subprocess
    try:
        if platform.system() == "Windows":
            # Method 1: SMBIOSMemoryType
            try:
                out = subprocess.check_output(
                    ["wmic","memorychip","get","SMBIOSMemoryType,Speed"],
                    stderr=subprocess.PIPE, text=True, timeout=5,
                    creationflags=0x08000000
                )
                # Parse line by line — first column is SMBIOSMemoryType
                lines = [l.strip() for l in out.splitlines() if l.strip() and not l.strip().startswith("S")]
                for line in lines:
                    parts = line.split()
                    if parts:
                        try:
                            smbios = int(parts[0])
                            if smbios == 34: return "DDR5"
                            if smbios in [26,27,28,29,30]: return "DDR4"
                            if smbios in [24,25]: return "DDR3"
                            if smbios in [21,22]: return "DDR2"
                        except ValueError:
                            pass
            except Exception:
                pass
            # Method 2: Speed only
            try:
                out = subprocess.check_output(
                    ["wmic","memorychip","get","Speed"],
                    stderr=subprocess.PIPE, text=True, timeout=5,
                    creationflags=0x08000000
                )
                speeds = [int(x) for x in out.split() if x.isdigit() and int(x) > 100]
                if speeds:
                    avg = sum(speeds)/len(speeds)
                    if avg >= 4800: return "DDR5"
                    if avg >= 2133: return "DDR4"
                    if avg >= 800:  return "DDR3"
                    return "DDR2"
            except Exception:
                pass
        elif platform.system() == "Linux":
            try:
                out = subprocess.check_output(
                    ["sudo","dmidecode","-t","memory"],
                    capture_output=True, text=True, timeout=5
                )
                for line in out.splitlines():
                    if "Type:" in line and "DDR" in line:
                        for t in ["DDR5","DDR4","DDR3","DDR2"]:
                            if t in line: return t
            except Exception:
                pass
            # Linux fallback: /sys
            try:
                import glob
                for path in glob.glob("/sys/bus/i2c/drivers/ee1004/*/eeprom"):
                    data = open(path,"rb").read()
                    if len(data) > 2:
                        t = data[2]
                        if t == 0x1e: return "DDR5"
                        if t == 0x0c: return "DDR4"
                        if t == 0x0b: return "DDR3"
                        if t == 0x08: return "DDR2"
            except Exception:
                pass
    except Exception:
        pass
    return "DDR4"

def detect_os():
    import platform
    try:
        s = platform.system()
        if s == "Windows":
            v = platform.version()
            r = platform.release()
            return f"Windows {r} ({v[:10]})"
        elif s == "Linux":
            try:
                for line in open("/etc/os-release"):
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=")[1].strip().strip('"')[:40]
            except:
                pass
            return f"Linux {platform.release()[:20]}"
        elif s == "Darwin":
            return f"macOS {platform.mac_ver()[0]}"
        return s
    except:
        return "unknown"

def detect_cpu():
    import platform, subprocess
    try:
        if platform.system() == "Windows":
            # Try registry first
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                    r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
                if name: return name[:40]
            except Exception:
                pass
            # Fallback WMIC
            try:
                out = subprocess.check_output(
                    ["wmic","cpu","get","name"],
                    stderr=subprocess.PIPE, text=True, timeout=5,
                    creationflags=0x08000000
                )
                lines = [l.strip() for l in out.splitlines() if l.strip() and l.strip() != "Name"]
                if lines: return lines[0][:40]
            except Exception:
                pass
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                for line in f:
                    if "model name" in line:
                        return line.split(":")[1].strip()[:40]
        elif platform.system() == "Darwin":
            out = subprocess.check_output(
                ["sysctl","-n","machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            if out: return out.strip()[:40]
    except Exception:
        pass
    return ""

def detect_ram_speed():
    """Get RAM speed in MHz to determine DDR type"""
    import platform, subprocess
    try:
        if platform.system() == "Windows":
            out = subprocess.check_output(
                ["wmic","memorychip","get","Speed"],
                stderr=subprocess.PIPE, text=True, timeout=5,
                creationflags=0x08000000
            )
            speeds = [int(x) for x in out.split() if x.isdigit() and int(x) > 100]
            if speeds: return sum(speeds)//len(speeds)
    except:
        pass
    return 0

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

def memory_walk(buf, prev_hash, address, nonce, steps=100000):
    """Exact same algorithm as polm.py — sha3 each step, measures real latency"""
    size = len(buf)
    seed = hashlib.sha3_256(f"{prev_hash}:{address}:{nonce}".encode()).digest()
    h    = seed
    pos  = int.from_bytes(h[:8], "little") % size
    t0   = time.perf_counter_ns()
    for _ in range(steps):
        mem = bytes(buf[pos:pos+32]) if pos+32 <= size else bytes(buf[pos:]) + bytes(buf[:32-(size-pos)])
        h   = hashlib.sha3_256(h + mem).digest()
        pos = int.from_bytes(h[:8], "little") % size
    avg_lat = (time.perf_counter_ns() - t0) / steps
    return h, avg_lat

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

RAM_TYPE = detect_ram()
CPU_NAME = detect_cpu()
OS_NAME  = detect_os()

check_update()

print("=" * 52)
print(f"  PoLM Miner CLI v{VERSION} — score = 1/latency_ns")
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
print(f"  RAM:     {RAM_TYPE}")
print(f"  CPU:     {CPU_NAME or 'unknown'}")
print(f"  OS:      {OS_NAME}")
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
            walk_h, lat = memory_walk(dag, prev_hash, polm_addr, nonce)
            if lat < 5:
                nonce += 1
                continue
            mem_proof = walk_h.hex()
            score = 1.0 / lat if lat > 0 else 0
            ts    = int(time.time())
            header = (f"{height}|{prev_hash}|{ts}|{nonce}|{polm_addr}|"
                      f"{RAM_TYPE}|1|{epoch}|{diff}|{lat:.4f}|{mem_proof}|"
                      f"{score:.8f}|{reward}|")
            block_hash = hashlib.sha3_256(header.encode()).hexdigest()

            if block_hash.startswith("0" * diff):
                # Verify height is still current before submitting
                try:
                    current = json.loads(urllib.request.urlopen(f"{NODE_URL}/getwork", timeout=3).read())
                    if int(current.get("height", height)) != height:
                        print(f"\n  Block found but chain moved — discarding")
                        break
                except Exception:
                    pass
                print(f"\n  Block found! nonce={nonce} hash={block_hash[:16]}...")
                bd = {
                    "height": height, "prev_hash": prev_hash,
                    "timestamp": ts, "nonce": nonce, "miner_id": polm_addr,
                    "ram_type": RAM_TYPE, "threads": 1, "epoch": epoch,
                    "difficulty": diff, "latency_ns": lat, "mem_proof": mem_proof,
                    "score": score, "reward": reward, "cpu_name": CPU_NAME, "os_name": OS_NAME,
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
