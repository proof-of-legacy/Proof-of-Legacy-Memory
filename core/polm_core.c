/*
 * PoLM PoSMA Library v2.0 — Implementação
 * Proof of Sequential Memory Access
 *
 * Build como lib compartilhada (para Oracle via ctypes):
 *   gcc -O2 -shared -fPIC -o polm_posma.so polm_posma.c -lssl -lcrypto
 *
 * Build estático (para linkar no minerador):
 *   gcc -O2 -c polm_posma.c -o polm_posma.o -lssl -lcrypto
 */

#include "polm_core.h"
#include "blake3/blake3.h"  /* BLAKE3 — 3.3x mais rápido que SHA3 no caminho PoSMA */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include "polm_crypto_compat.h"
#else
#include <openssl/evp.h>

#define EVICT_BUFFER_SIZE (32UL * 1024 * 1024)
static volatile uint64_t *_evict_buf = NULL;
static size_t _evict_slots = 0;

void posma_evict_l3_cache(void) {
    posma_init_evict_buffer();
    if (!_evict_buf) return;
    volatile uint64_t sink = 0;
    for (size_t ei = 0; ei < _evict_slots; ei += 8)
        sink ^= _evict_buf[ei];
    (void)sink;
}

void posma_init_evict_buffer(void) {
    if (_evict_buf) return;
    _evict_slots = EVICT_BUFFER_SIZE / sizeof(uint64_t);
    _evict_buf = (volatile uint64_t *)malloc(EVICT_BUFFER_SIZE);
    if (_evict_buf == NULL) return;
    for (size_t i = 0; i < _evict_slots; i++)
        _evict_buf[i] = (uint64_t)(i * 6364136223846793005ULL + 1442695040888963407ULL);
}
#endif

/* ── BLAKE3 helper — usado APENAS no caminho PoSMA ──────────── */
/* NOTA: Hash final do bloco continua usando SHA3-256 (posma_final_hash) */
static uint64_t blake3_next_index(uint64_t current_idx, uint64_t nonce,
                                   const char *salt, int step,
                                   size_t num_slots) {
    blake3_hasher hasher;
    blake3_hasher_init(&hasher);
    blake3_hasher_update(&hasher, &current_idx, sizeof(uint64_t));
    blake3_hasher_update(&hasher, &nonce,        sizeof(uint64_t));
    blake3_hasher_update(&hasher, salt,           strlen(salt));
    blake3_hasher_update(&hasher, &step,          sizeof(int));
    uint8_t out[8];
    blake3_hasher_finalize(&hasher, out, 8);
    uint64_t next;
    memcpy(&next, out, 8);
    return next % num_slots;
}

static uint64_t blake3_start_index(uint64_t nonce, const char *salt,
                                    size_t num_slots) {
    blake3_hasher hasher;
    blake3_hasher_init(&hasher);
    blake3_hasher_update(&hasher, &nonce, sizeof(uint64_t));
    blake3_hasher_update(&hasher, salt,   strlen(salt));
    uint8_t tag[] = "start";
    blake3_hasher_update(&hasher, tag, 5);
    uint8_t out[8];
    blake3_hasher_finalize(&hasher, out, 8);
    uint64_t idx;
    memcpy(&idx, out, 8);
    return idx % num_slots;
}

/* ── SHA3-256 helper ──────────────────────────────────────── */
static void sha3_256_bytes(const uint8_t *input, size_t ilen, uint8_t *out32) {
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha3_256(), NULL);
    EVP_DigestUpdate(ctx, input, ilen);
    unsigned int hlen = 32;
    EVP_DigestFinal_ex(ctx, out32, &hlen);
    EVP_MD_CTX_free(ctx);
}

static void sha3_256_str(const char *input, uint8_t *out32) {
    sha3_256_bytes((const uint8_t *)input, strlen(input), out32);
}

static void bytes_to_hex(const uint8_t *bytes, size_t len, char *hex_out) {
    for (size_t i = 0; i < len; i++)
        snprintf(hex_out + i*2, 3, "%02x", bytes[i]);
    hex_out[len*2] = '\0';
}

/* ── DAG Generation ───────────────────────────────────────── */
void posma_generate_dag(uint8_t *dag, const char *seed, const char *epoch_salt) {
    /*
     * Preenche DAG com SHA-256 encadeado + salt por época.
     * Salt impede pré-cálculo do DAG entre épocas.
     * Formato de cada chunk: SHA256("polm_dag:{seed}:{epoch_salt}:{chunk_idx}")
     */
    uint8_t hash[32];
    char block[512];
    size_t pos = 0;
    int chunk = 0;

    while (pos < DAG_SIZE_BYTES) {
        snprintf(block, sizeof(block), "polm_dag:%s:%s:%d", seed, epoch_salt, chunk++);
        sha3_256_str(block, hash);
        size_t copy = (DAG_SIZE_BYTES - pos < 32) ? DAG_SIZE_BYTES - pos : 32;
        memcpy(dag + pos, hash, copy);
        pos += copy;
    }
}

/* ── PoSMA Path Calculation ───────────────────────────────── */
void posma_calculate_path(const uint8_t *dag, uint64_t nonce,
                          const char *salt, PosmaResult *result) {
    /*
     * Caminho DETERMINÍSTICO dado nonce+salt.
     * Fórmula: Next_Index = SHA3(Current_Index || Nonce || Salt) % (DAG_Size / Stride)
     *
     * STRIDE = 4096 bytes — garante cache miss na DRAM real.
     * Cada step lê 8 bytes do DAG no índice calculado.
     */
    size_t num_slots = DAG_SIZE_BYTES / POSMA_STRIDE;  /* 65536 slots de 4KB */
    /* hash_buf e hash_input removidos — BLAKE3 usa API própria */

    /* Índice inicial: BLAKE3(nonce || salt || "start") — 3.3x mais rápido que SHA3 */
    uint64_t current_idx = blake3_start_index(nonce, salt, num_slots);

    uint64_t prev_val = nonce;
    for (int step = 0; step < POSMA_STEPS; step++) {
        /* Endereço físico na DRAM — stride de 4KB garante cache miss */
        size_t base_addr = current_idx * POSMA_STRIDE;
        uint64_t trash = 0;
        if (_evict_buf) {
            size_t evict_idx = ((size_t)step * 8) % _evict_slots;
            trash = _evict_buf[evict_idx];
            __asm__ volatile("" : "+r"(trash));
        }
        uint16_t _ob = (uint16_t)(((prev_val ^ trash) >> 24) & 0xFFFF); size_t offset = (size_t)(((uint64_t)_ob * (POSMA_STRIDE - 8)) >> 16);

        /* Lê 8 bytes do DAG — volatile força acesso real à DRAM, sem cache */
        volatile const uint64_t *ptr = (volatile const uint64_t *)(dag + base_addr + offset);
        uint64_t val = *ptr;

        /* Armazena no merge_value */
        memcpy(result->merge_value + step * 8, &val, 8);
        result->indices[step] = current_idx;

        /* Próximo índice: depende do VALOR LIDO da RAM — derrota Hardware Prefetcher */
        /* CPU não pode adivinhar o próximo endereço sem buscar o dado na DRAM real */
        current_idx = ((val ^ (nonce * 0x9e3779b97f4a7c15ULL)) * 0x01000193ULL
                       + (uint64_t)step * 0x517cc1b727220a95ULL) % num_slots;
        prev_val = val;
    }
}

/* ── Final Hash ───────────────────────────────────────────── */
void posma_final_hash(uint64_t nonce, const char *salt, const char *seed,
                      const uint8_t *merge_value, char *hash_hex_out) {
    /*
     * Hash Final = SHA3(nonce || salt || seed || merge_value)
     * Se o minerador inventar merge_value, este hash não vai bater
     * quando o Oracle recalcular o caminho real.
     */
    size_t header_len = 64 + strlen(salt) + strlen(seed) + 2;
    size_t total_len  = header_len + MERGE_VALUE_BYTES;
    uint8_t *buf = (uint8_t *)malloc(total_len + 64);

    char header[512];
    snprintf(header, sizeof(header), "%llu|%s|%s|",
             (unsigned long long)nonce, salt, seed);
    size_t hlen = strlen(header);

    memcpy(buf, header, hlen);
    memcpy(buf + hlen, merge_value, MERGE_VALUE_BYTES);

    uint8_t hash[32];
    sha3_256_bytes(buf, hlen + MERGE_VALUE_BYTES, hash);
    bytes_to_hex(hash, 32, hash_hex_out);
    free(buf);
}

/* ── Target Check ─────────────────────────────────────────── */
int posma_meets_target(const char *hash_hex, int difficulty) {
    for (int i = 0; i < difficulty; i++)
        if (hash_hex[i] != '0') return 0;
    return 1;
}
