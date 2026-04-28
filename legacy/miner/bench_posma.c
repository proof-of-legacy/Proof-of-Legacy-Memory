#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "polm_posma.h"

#define DAG_SIZE_BYTES (256 * 1024 * 1024)

int main(void) {
    uint8_t *dag = malloc(DAG_SIZE_BYTES);
    if (!dag) { printf("malloc falhou\n"); return 1; }

    posma_init_evict_buffer();
    printf("Eviction buffer inicializado (32MB)\n");

    const char *seed = "polm:0:0000abc123def456";
    const char *salt = "epoch_0_0000abc123def456";
    printf("Gerando DAG (256MB)...\n");
    posma_generate_dag(dag, seed, salt);
    printf("DAG pronto. Rodando benchmark...\n");

    PosmaResult result;
    int N = 10;
    struct timespec t0, t1;

    clock_gettime(CLOCK_MONOTONIC_RAW, &t0);
    for (int i = 0; i < N; i++)
        posma_calculate_path(dag, (uint64_t)i + 1000, salt, &result);
    clock_gettime(CLOCK_MONOTONIC_RAW, &t1);

    double total_ms = (t1.tv_sec - t0.tv_sec) * 1000.0 + (t1.tv_nsec - t0.tv_nsec) / 1e6;
    double per_loop_ms = total_ms / N;
    double per_step_ns = (per_loop_ms * 1e6) / 1000.0;

    printf("=== RESULTADO ===\n");
    printf("Total: %.2f ms (%d loops)\n", total_ms, N);
    printf("Por loop: %.3f ms\n", per_loop_ms);
    printf("Por step (1000 steps): %.0f ns\n", per_step_ns);

    if (per_step_ns < 100)
        printf("STATUS: CACHE L2/L3 — eviction nao funcionou\n");
    else if (per_step_ns < 300)
        printf("STATUS: DRAM REAL DDR4 — algoritmo funcionando!\n");
    else
        printf("STATUS: DRAM + TLB miss — aceitavel\n");

    free(dag);
    return 0;
}
