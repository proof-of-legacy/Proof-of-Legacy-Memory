#!/usr/bin/env python3
"""
PoLM Bridge Oracle v2.0 -- Native -> Polygon ERC-20
https://polm.com.br

Monitors native PoLM blockchain and registers mined blocks
on the Polygon POLMToken contract via ECDSA signatures.

Setup:
  1. Configure .env with ORACLE_PRIVATE_KEY and POLM_CONTRACT
  2. python3 polm_bridge_oracle.py setup
  3. python3 polm_bridge_oracle.py run
"""

import os, json, time, logging, sys
from typing import Optional

def load_env():
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        for line in open(env_file):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

ORACLE_PRIVATE_KEY = os.environ.get('ORACLE_PRIVATE_KEY', '')
POLM_CONTRACT_ADDR = os.environ.get('POLM_CONTRACT', '')
POLM_NODE_URL      = os.environ.get('POLM_NODE_URL', 'http://localhost:6060')
POLYGON_RPC        = os.environ.get('POLYGON_RPC', 'https://polygon-rpc.com')

CHECK_INTERVAL_S = 60
BATCH_INTERVAL_S = 86400  # send to Polygon once per day

STATE_FILE   = '/root/.polm/oracle_polygon_state.json'
EVM_MAP_FILE = '/root/.polm/evm_addresses.json'
LOG_FILE     = '/var/log/polm-oracle.log'

os.makedirs('/root/.polm', exist_ok=True)
os.makedirs('/var/log', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Oracle] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger('oracle')

CONTRACT_ABI = [
    {
        "inputs": [
            {"name": "blockHashes", "type": "bytes32[]"},
            {"name": "miners",      "type": "address[]"},
            {"name": "amounts",     "type": "uint256[]"},
            {"name": "signatures",  "type": "bytes[]"},
        ],
        "name": "registerBatch",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "blockHash",  "type": "bytes32"},
            {"name": "miner",      "type": "address"},
            {"name": "polmAmount", "type": "uint256"},
        ],
        "name": "buildMessageHash",
        "outputs": [{"name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "", "type": "bytes32"}],
        "name": "registeredBlocks",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]

import urllib.request

def fetch_node(path: str) -> Optional[dict]:
    try:
        r = urllib.request.urlopen(POLM_NODE_URL.rstrip('/') + path, timeout=10)
        return json.loads(r.read())
    except Exception as e:
        log.warning(f'Node fetch failed ({path}): {e}')
        return None

def get_chain_height() -> int:
    d = fetch_node('/')
    return int(d.get('height', 0)) if d else 0

def get_block(height: int) -> Optional[dict]:
    d = fetch_node(f'/block/{height}')
    if not d: return None
    return d.get('block', d)

def load_evm_map() -> dict:
    if os.path.exists(EVM_MAP_FILE):
        try: return json.load(open(EVM_MAP_FILE))
        except: pass
    return {}

def get_miner_evm(miner_polm: str) -> Optional[str]:
    # 1. Check local map
    evm_map = load_evm_map()
    if miner_polm in evm_map:
        return evm_map[miner_polm]
    # 2. Check node /register_evm endpoint
    d = fetch_node(f'/register_evm?polm_address={miner_polm}')
    if d and d.get('evm_address'):
        evm = d['evm_address']
        if len(evm) == 42 and evm.startswith('0x'):
            # Cache locally
            evm_map[miner_polm] = evm
            json.dump(evm_map, open(EVM_MAP_FILE, 'w'), indent=2)
            return evm
    # 3. Check /miners endpoint
    miners = fetch_node('/miners')
    if miners and miner_polm in miners:
        evm = miners[miner_polm].get('evm_address', '')
        if evm and len(evm) == 42 and evm.startswith('0x'):
            return evm
    return None

def register_evm(miner_polm: str, miner_evm: str):
    """Manually register EVM address for a miner."""
    evm_map = load_evm_map()
    evm_map[miner_polm] = miner_evm
    json.dump(evm_map, open(EVM_MAP_FILE, 'w'), indent=2)
    log.info(f'Registered: {miner_polm[:20]} -> {miner_evm}')

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try: return json.load(open(STATE_FILE))
        except: pass
    return {
        'last_processed_height': 0,
        'pending_blocks': [],
        'registered_hashes': [],
        'last_batch_time': 0,
    }

def save_state(state: dict):
    json.dump(state, open(STATE_FILE, 'w'), indent=2)

def sign_block(oracle_account, contract, w3,
               block_hash_hex: str, miner_evm: str, polm_amount: int) -> Optional[bytes]:
    try:
        from eth_account.messages import encode_defunct
        bh = bytes.fromhex(block_hash_hex.replace('0x', '').ljust(64, '0'))[:32]
        # Sign raw keccak256 -- contract adds eth prefix internally via toEthSignedMessageHash
        msg_hash = w3.solidity_keccak(
            ['bytes32', 'address', 'uint256', 'address'],
            [bh, w3.to_checksum_address(miner_evm), polm_amount, w3.to_checksum_address(POLM_CONTRACT_ADDR)]
        )
        signed = oracle_account.sign_message(encode_defunct(msg_hash))
        return signed.signature
    except Exception as e:
        log.error(f'Sign failed: {e}')
        return None

def send_chunk(w3, contract, oracle_account, chunk: list) -> list:
    """Send a single chunk of blocks."""
    block_hashes, miners, amounts, signatures = [], [], [], []
    for entry in chunk:
        try:
            bh = bytes.fromhex(entry['block_hash'].replace('0x', '').ljust(64, '0'))[:32]
            block_hashes.append(bh)
            miners.append(w3.to_checksum_address(entry['miner_evm']))
            amounts.append(entry['polm_amount'])
            signatures.append(bytes.fromhex(entry['signature']))
        except Exception as e:
            log.warning(f'Entry skipped: {e}')
    if not block_hashes:
        return []
    try:
        nonce     = w3.eth.get_transaction_count(oracle_account.address)
        gas_price = w3.eth.gas_price
        txn = contract.functions.registerBatch(
            block_hashes, miners, amounts, signatures
        ).build_transaction({
            'from':     oracle_account.address,
            'nonce':    nonce,
            'gasPrice': gas_price,
            'gas':      800_000,
            'chainId':  137,
        })
        signed_txn = oracle_account.sign_transaction(txn)
        tx_hash    = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        log.info(f'Chunk tx: {tx_hash.hex()}')
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status == 1:
            log.info(f'Chunk confirmed! Gas: {receipt.gasUsed}')
            return [e['block_hash'] for e in chunk]
        else:
            log.error('Chunk failed!')
            return []
    except Exception as e:
        log.error(f'Chunk send failed: {e}')
        return []

def send_batch(w3, contract, oracle_account, pending_blocks: list) -> list:
    if not pending_blocks:
        return []

    CHUNK_SIZE = 50  # max per tx to stay under 131KB limit
    registered = []
    chunks = [pending_blocks[i:i+CHUNK_SIZE] for i in range(0, len(pending_blocks), CHUNK_SIZE)]
    log.info(f'Sending {len(pending_blocks)} blocks in {len(chunks)} chunks...')

    for i, chunk in enumerate(chunks):
        log.info(f'Chunk {i+1}/{len(chunks)} ({len(chunk)} blocks)...')
        result = send_chunk(w3, contract, oracle_account, chunk)
        registered.extend(result)
        if result:
            time.sleep(3)
        else:
            log.error(f'Chunk {i+1} failed — stopping')
            break

    log.info(f'Batch done: {len(registered)}/{len(pending_blocks)} registered')
    return registered

def run():
    log.info('=' * 50)
    log.info('PoLM Bridge Oracle v2.0 -- Polygon')
    log.info(f'Node:     {POLM_NODE_URL}')
    log.info(f'Contract: {POLM_CONTRACT_ADDR}')
    log.info('=' * 50)

    if not ORACLE_PRIVATE_KEY:
        log.error('ORACLE_PRIVATE_KEY not set!')
        sys.exit(1)
    if not POLM_CONTRACT_ADDR:
        log.error('POLM_CONTRACT not set!')
        sys.exit(1)

    try:
        from eth_account import Account
        from web3 import Web3
        from web3.middleware import ExtraDataToPOAMiddleware
    except ImportError:
        log.error('Run: pip install web3 eth-account')
        sys.exit(1)

    oracle_account = Account.from_key(ORACLE_PRIVATE_KEY)
    log.info(f'Oracle: {oracle_account.address}')

    w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        log.error('Cannot connect to Polygon!')
        sys.exit(1)

    balance = w3.from_wei(w3.eth.get_balance(oracle_account.address), 'ether')
    log.info(f'Oracle balance: {balance:.4f} MATIC')
    if balance < 0.01:
        log.warning(f'Low MATIC! Fund: {oracle_account.address}')

    contract = w3.eth.contract(
        address=w3.to_checksum_address(POLM_CONTRACT_ADDR),
        abi=CONTRACT_ABI
    )

    state = load_state()
    log.info(f'Resuming from height {state["last_processed_height"]}')

    while True:
        try:
            current_height = get_chain_height()

            if current_height > state['last_processed_height']:
                for height in range(state['last_processed_height'] + 1, current_height + 1):
                    block = get_block(height)
                    if not block:
                        continue

                    block_hash = block.get('block_hash', '')
                    miner_polm = block.get('miner_id', '')
                    reward     = float(block.get('reward', 0))

                    if miner_polm == 'GENESIS' or height == 0:
                        state['last_processed_height'] = height
                        continue

                    if block_hash in state['registered_hashes']:
                        state['last_processed_height'] = height
                        continue

                    miner_evm = get_miner_evm(miner_polm)
                    if not miner_evm:
                        log.warning(f'Block #{height}: no EVM for {miner_polm[:20]}')
                        state['last_processed_height'] = height
                        continue

                    polm_amount = int(reward * 10**8)
                    sig = sign_block(oracle_account, contract, w3,
                                     block_hash, miner_evm, polm_amount)
                    if not sig:
                        continue

                    state['pending_blocks'].append({
                        'height':      height,
                        'block_hash':  block_hash,
                        'miner_polm':  miner_polm,
                        'miner_evm':   miner_evm,
                        'polm_amount': polm_amount,
                        'reward':      reward,
                        'signature':   sig.hex(),
                        'signed_at':   int(time.time()),
                    })
                    log.info(f'Signed #{height} -- {miner_evm[:16]}... {reward} POLM')
                    state['last_processed_height'] = height

                save_state(state)

            # Batch to Polygon
            time_since = time.time() - state['last_batch_time']
            if state['pending_blocks'] and time_since >= BATCH_INTERVAL_S:
                registered = send_batch(w3, contract, oracle_account, state['pending_blocks'])
                if registered:
                    state['registered_hashes'].extend(registered)
                    state['pending_blocks'] = [
                        b for b in state['pending_blocks']
                        if b['block_hash'] not in registered
                    ]
                    state['last_batch_time'] = int(time.time())
                    save_state(state)

            log.info(
                f'Height={current_height} Pending={len(state["pending_blocks"])} '
                f'NextBatch={max(0, int((BATCH_INTERVAL_S - time_since)/3600))}h'
            )

        except KeyboardInterrupt:
            log.info('Stopping...')
            save_state(state)
            break
        except Exception as e:
            log.error(f'Error: {e}')

        time.sleep(CHECK_INTERVAL_S)

def status():
    state = load_state()
    print(f'\nOracle Status')
    print(f'Last height:   {state["last_processed_height"]}')
    print(f'Pending:       {len(state["pending_blocks"])} blocks')
    print(f'Registered:    {len(state["registered_hashes"])} blocks')
    last = state["last_batch_time"]
    print(f'Last batch:    {time.ctime(last) if last else "never"}')
    d = fetch_node('/')
    if d:
        print(f'Node height:   {d.get("height")}')
        print(f'Node supply:   {d.get("total_supply")} POLM')
    evm_map = load_evm_map()
    print(f'EVM mappings:  {len(evm_map)} miners registered')

def setup():
    print('\nPoLM Oracle Setup')
    print('=' * 40)
    os.system('/opt/polm/venv/bin/pip install web3 eth-account --quiet')
    if ORACLE_PRIVATE_KEY:
        from eth_account import Account
        acc = Account.from_key(ORACLE_PRIVATE_KEY)
        print(f'Oracle: {acc.address}')
    else:
        print('ORACLE_PRIVATE_KEY not set!')
    print(f'Contract: {POLM_CONTRACT_ADDR or "NOT SET"}')
    print(f'Node:     {POLM_NODE_URL}')
    print('Setup complete!')

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'run'
    if cmd == 'run':
        run()
    elif cmd == 'status':
        status()
    elif cmd == 'setup':
        setup()
    elif cmd == 'register':
        # Usage: python3 polm_bridge_oracle.py register POLM_ADDRESS EVM_ADDRESS
        if len(sys.argv) >= 4:
            register_evm(sys.argv[2], sys.argv[3])
        else:
            print('Usage: register <POLM_ADDRESS> <EVM_ADDRESS>')
    else:
        print('Usage: python3 polm_bridge_oracle.py [run|status|setup|register]')
