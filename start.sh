#!/bin/bash
cd ~/Proof-of-Legacy-Memory
kill $(lsof -t -i:5555) 2>/dev/null
sleep 2
scp aluisio@192.168.0.103:~/Proof-of-Legacy-Memory/polm_chain.db . 2>/dev/null
scp aluisio@192.168.0.103:~/Proof-of-Legacy-Memory/polm_utxo.db . 2>/dev/null
python3 polm_node.py --ram-type DDR4 >> polm_node.log 2>&1
