/*
 * PoLM PoSMA Library v2.0 — Proof of Sequential Memory Access
 * Core algorithm shared between miner (C) and oracle (Python via ctypes)
 *
 * REGRAS INVIOLÁVEIS (do documento v2):
 *   - Stride mínimo: 4096 bytes (força cache miss na DRAM real)
 *   - Passos: 1000 por bloco
 *   - Hash: SHA3-256 via OpenSSL
 *   - Caminho: determinístico dado nonce+salt+dag_seed
 */

#ifndef POLM_CORE_H
#define POLM_CORE_H

#include <stdint.h>
#include <stddef.h>

#define POSMA_STEPS        10000
#define POSMA_STRIDE       4096      /* bytes — força acesso à DRAM */
#define DAG_SIZE_MB        256
#define DAG_SIZE_BYTES     ((size_t)DAG_SIZE_MB * 1024 * 1024)
#define MERGE_VALUE_BYTES  (POSMA_STEPS * 8)   /* 8 bytes por passo = 8000 bytes */

/* Resultado de um caminho PoSMA */
typedef struct {
    uint8_t  merge_value[MERGE_VALUE_BYTES];  /* 8000 bytes lidos da RAM */
    char     hash_final[65];                  /* SHA3-256 hex do bloco */
    uint64_t indices[POSMA_STEPS];            /* índices percorridos (debug) */
} PosmaResult;

/* Gera o DAG de 256MB — preenche buf (deve ter DAG_SIZE_BYTES) */
void posma_generate_dag(uint8_t *dag, const char *seed, const char *epoch_salt);

/* Calcula o caminho determinístico e preenche result */
void posma_calculate_path(const uint8_t *dag, uint64_t nonce,
                          const char *salt, PosmaResult *result);

/* Gera o hash final do bloco */
void posma_final_hash(uint64_t nonce, const char *salt, const char *seed,
                      const uint8_t *merge_value, char *hash_hex_out);

/* Verifica se hash_final começa com 'difficulty' zeros */
int posma_meets_target(const char *hash_hex, int difficulty);

/* Inicializa eviction buffer 32MB para anti-prefetch nivel 4 */
void posma_init_evict_buffer(void);
void posma_evict_l3_cache(void);
#endif /* POLM_CORE_H */
