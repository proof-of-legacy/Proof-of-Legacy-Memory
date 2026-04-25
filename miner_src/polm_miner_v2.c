/*
 * PoLM Miner C v3.0.0 — Proof of Real Memory (PoRM)
 * Implementa PoSMA: prova criptográfica de acesso físico à RAM
 *
 * Build:
 *   sudo apt install libssl-dev libcurl4-openssl-dev
 *   gcc -O2 -o polm_miner_v2 polm_miner_v2.c polm_posma.c -lssl -lcrypto -lcurl -lm
 *
 * Usage:
 *   ./polm_miner_v2 <POLM_ADDRESS> [NODE_URL]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <time.h>
#include <signal.h>
#include <unistd.h>
#ifndef _WIN32
#include <sys/mman.h>
#endif
#include <curl/curl.h>
#include "../core/polm_core.h"

#define VERSION      "3.0.1"
#define NONCE_MIN    100

/* ── Globals ──────────────────────────────────────────────── */
static volatile int running = 1;
static uint8_t *dag = NULL;  /* alocado com Huge Pages ou malloc */
static char    current_dag_key[256] = {0};

/* ── CPU detection ────────────────────────────────────────── */
static void get_cpu_name(char *out, size_t maxlen) {
#ifdef __linux__
    FILE *f = fopen("/proc/cpuinfo", "r");
    if (f) {
        char line[256];
        while (fgets(line, sizeof(line), f)) {
            if (strncmp(line, "model name", 10) == 0) {
                char *p = strchr(line, ':');
                if (p) {
                    p += 2;
                    /* Remove trailing newline */
                    size_t len = strlen(p);
                    if (len > 0 && p[len-1] == '\n') p[len-1] = '\0';
                    /* Clean up Intel/AMD verbose names */
                    char *r;
                    while ((r = strstr(p, "(R)")) != NULL) memmove(r, r+3, strlen(r+3)+1);
                    while ((r = strstr(p, "(TM)")) != NULL) memmove(r, r+4, strlen(r+4)+1);
                    while ((r = strstr(p, "CPU @ ")) != NULL) { *r = '\0'; break; }
                    /* Trim spaces */
                    while (*p == ' ') p++;
                    len = strlen(p);
                    while (len > 0 && p[len-1] == ' ') p[--len] = '\0';
                    snprintf(out, maxlen, "%s", p);
                    fclose(f);
                    return;
                }
            }
        }
        fclose(f);
    }
#endif
    snprintf(out, maxlen, "Unknown CPU");
}

/* ── HTTP ─────────────────────────────────────────────────── */
typedef struct { char *data; size_t len; } HttpBuf;

static size_t curl_cb(void *ptr, size_t size, size_t nmemb, HttpBuf *buf) {
    size_t real = size * nmemb;
    buf->data = realloc(buf->data, buf->len + real + 1);
    memcpy(buf->data + buf->len, ptr, real);
    buf->len += real;
    buf->data[buf->len] = '\0';
    return real;
}

static char *http_get(const char *url) {
    CURL *curl = curl_easy_init();
    if (!curl) return NULL;
    HttpBuf buf = { calloc(1,1), 0 };
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buf);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 60L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    CURLcode res = curl_easy_perform(curl);
    curl_easy_cleanup(curl);
    if (res != CURLE_OK) { free(buf.data); return NULL; }
    return buf.data;
}

static char *http_post(const char *url, const char *json) {
    CURL *curl = curl_easy_init();
    if (!curl) return NULL;
    HttpBuf buf = { calloc(1,1), 0 };
    struct curl_slist *hdrs = curl_slist_append(NULL, "Content-Type: application/json");
    curl_easy_setopt(curl, CURLOPT_URL, url);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, hdrs);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &buf);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 60L);
    curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
    CURLcode res = curl_easy_perform(curl);
    curl_slist_free_all(hdrs);
    curl_easy_cleanup(curl);
    if (res != CURLE_OK) { free(buf.data); return NULL; }
    return buf.data;
}

/* ── JSON helpers ─────────────────────────────────────────── */
static int json_int(const char *json, const char *key) {
    char pat[128]; snprintf(pat, sizeof(pat), "\"%s\":", key);
    const char *p = strstr(json, pat);
    if (!p) return 0;
    p += strlen(pat);
    while (*p == ' ') p++;
    return atoi(p);
}

static double json_double(const char *json, const char *key) {
    char pat[128]; snprintf(pat, sizeof(pat), "\"%s\":", key);
    const char *p = strstr(json, pat);
    if (!p) return 0.0;
    p += strlen(pat);
    while (*p == ' ') p++;
    return atof(p);
}

static void json_str(const char *json, const char *key, char *out, size_t maxlen) {
    char pat[128]; snprintf(pat, sizeof(pat), "\"%s\":\"", key);
    const char *p = strstr(json, pat);
    if (!p) { out[0]='\0'; return; }
    p += strlen(pat);
    size_t i = 0;
    while (*p && *p != '"' && i < maxlen-1) out[i++] = *p++;
    out[i] = '\0';
}

/* ── rdtscp — medição sub-nanosegundo sem syscall ────────── */
static inline uint64_t rdtscp_read(void) {
    uint32_t lo, hi;
    __asm__ volatile ("rdtscp" : "=a"(lo), "=d"(hi) :: "%rcx");
    return ((uint64_t)hi << 32) | lo;
}

/* Calibrar TSC: medir quantos ciclos por nanosegundo */
static double tsc_ghz = 0.0;

static void calibrate_tsc(void) {
    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    uint64_t c0 = rdtscp_read();
    /* Esperar 100ms */
    struct timespec req = {0, 100000000L};
    nanosleep(&req, NULL);
    uint64_t c1 = rdtscp_read();
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double ns = (t1.tv_sec - t0.tv_sec) * 1e9 + (t1.tv_nsec - t0.tv_nsec);
    tsc_ghz = (double)(c1 - c0) / ns;
    printf("  TSC: %.3f GHz (calibrado)\n", tsc_ghz);
}

/* ── DRAM Latency Measurement (Pointer-Chasing + rdtscp) ──── */
static double polm_measure_dram_ns(uint64_t nonce) {
    size_t num_slots   = DAG_SIZE_BYTES / POSMA_STRIDE;
    size_t stride_u64  = POSMA_STRIDE / sizeof(uint64_t);
    uint64_t *dag64    = (uint64_t *)dag;
    volatile uint64_t idx = (nonce ^ 0xdeadbeef1234ULL) % num_slots;

            /* Evict L3 cache antes de medir — força acesso real a DRAM */
    posma_evict_l3_cache();
    /* Pointer-chasing com rdtscp — DAG fora da cache L3 */
    uint64_t c0 = rdtscp_read();
    for (int i = 0; i < 200; i++) {
        uint64_t val = dag64[idx * stride_u64];
        idx = (idx ^ val ^ (uint64_t)i) % num_slots;
    }
    uint64_t c1 = rdtscp_read();
    (void)idx;

    /* Ciclos → nanosegundos usando TSC calibrado */
    return (double)(c1 - c0) / (tsc_ghz * 200.0);
}

/* ── Signal ───────────────────────────────────────────────── */
static void sig_handler(int s) { (void)s; running = 0; }

/* ── Hex encode merge_value para JSON ─────────────────────── */
static void merge_to_hex(const uint8_t *merge, char *hex_out) {
    for (int i = 0; i < MERGE_VALUE_BYTES; i++)
        snprintf(hex_out + i*2, 3, "%02x", merge[i]);
    hex_out[MERGE_VALUE_BYTES * 2] = '\0';
}


#ifdef _WIN32
#include "polm_crypto_compat.h"
#else
#include <openssl/sha.h>
/* Linux helpers — equivalentes ao polm_crypto_compat.h */
static inline const char* get_home_dir(void) {
    const char *h = getenv("HOME");
    return h ? h : ".";
}
static inline int read_random_bytes(uint8_t *buf, size_t len) {
    FILE *f = fopen("/dev/urandom", "rb");
    if (!f || fread(buf, 1, len, f) != len) { if(f) fclose(f); return 0; }
    fclose(f); return 1;
}
#endif
/* ── Geração de carteira POLM ─────────────────────────────── */
static void generate_polm_wallet(char *addr_out, size_t addr_len) {
    uint8_t priv[32];
    
    if (!read_random_bytes(priv, 32)) {
        fprintf(stderr, "Erro ao gerar carteira\n"); exit(1);
    }
    uint8_t hash[32];
    SHA256_CTX ctx;
    SHA256_Init(&ctx);
    SHA256_Update(&ctx, priv, 32);
    SHA256_Final(hash, &ctx);
    snprintf(addr_out, addr_len, "POLM");
    for (int i = 0; i < 16; i++)
        snprintf(addr_out + 4 + i*2, addr_len - 4 - i*2, "%02X", hash[i]);
    char wf_path[512];
    snprintf(wf_path, sizeof(wf_path), "%s/.polm_wallet", get_home_dir());
    FILE *wf = fopen(wf_path, "w");
    if (wf) { fprintf(wf, "address=%s\n", addr_out); fclose(wf); }
}

static int load_polm_wallet(char *addr_out, size_t addr_len) {
    char wf_path[512];
    snprintf(wf_path, sizeof(wf_path), "%s/.polm_wallet", get_home_dir());
    FILE *wf = fopen(wf_path, "r");
    if (!wf) return 0;
    char line[256];
    while (fgets(line, sizeof(line), wf)) {
        if (strncmp(line, "address=", 8) == 0) {
            line[strcspn(line, "\n")] = 0;
            strncpy(addr_out, line + 8, addr_len - 1);
            fclose(wf); return 1;
        }
    }
    fclose(wf); return 0;
}

/* ── Main ─────────────────────────────────────────────────── */
int main(int argc, char *argv[]) {
#ifdef _WIN32
    SetConsoleOutputCP(65001);
#endif
    const char *polm_addr = NULL;
    const char *node_url  = "https://polm.com.br/api";

    for (int i = 1; i < argc; i++) {
        if ((strcmp(argv[i], "--wallet") == 0 || strcmp(argv[i], "-w") == 0) && i+1 < argc)
            polm_addr = argv[++i];
        else if (strcmp(argv[i], "--api") == 0 && i+1 < argc)
            node_url = argv[++i];
        else if (argv[i][0] != '-' && !polm_addr)
            polm_addr = argv[i];
    }
    /* Onboarding interativo se sem carteira */
    static char wallet_buf[128] = {0};
    if (!polm_addr) {
        printf("\n====================================================\n");
        printf("  PoLM Miner v3.0.0 — Proof of Real Memory\n");
        printf("====================================================\n\n");
        if (load_polm_wallet(wallet_buf, sizeof(wallet_buf))) {
            printf("  Carteira salva: %s\n  Usar esta? [S/n]: ", wallet_buf);
            char resp[8] = {0};
            if (fgets(resp, sizeof(resp), stdin) && (resp[0]=='n'||resp[0]=='N'))
                wallet_buf[0] = 0;
            else
                polm_addr = wallet_buf;
        }
        if (!polm_addr) {
            printf("  Voce ja tem carteira POLM? [s/N]: ");
            char resp[8] = {0};
            fgets(resp, sizeof(resp), stdin);
            if (resp[0]=='s'||resp[0]=='S') {
                printf("  Digite seu endereco POLM: ");
                if (fgets(wallet_buf, sizeof(wallet_buf), stdin)) {
                    wallet_buf[strcspn(wallet_buf, "\n")] = 0;
                    polm_addr = wallet_buf;
                    char wf_path[512];
                    snprintf(wf_path, sizeof(wf_path), "%s/.polm_wallet", get_home_dir());
                    FILE *wf = fopen(wf_path, "w");
                    if (wf) { fprintf(wf, "address=%s\n", polm_addr); fclose(wf); }
                }
            } else {
                printf("\n  Gerando nova carteira POLM...\n");
                generate_polm_wallet(wallet_buf, sizeof(wallet_buf));
                polm_addr = wallet_buf;
                printf("  Endereco POLM: %s\n", polm_addr);
                printf("  IMPORTANTE: Anote este endereco para resgatar seus tokens!\n\n");
        printf("  Digite seu endereco Polygon/MetaMask (0x...) para resgatar tokens:\n");
        printf("  (Pressione Enter para pular por enquanto)\n  Polygon: ");
        static char poly_buf[128] = {0};
        if (fgets(poly_buf, sizeof(poly_buf), stdin)) {
            poly_buf[strcspn(poly_buf, "\n")] = 0;
            if (strlen(poly_buf) > 5) {
                char wf_path[512];
                snprintf(wf_path, sizeof(wf_path), "%s/.polm_wallet", get_home_dir());
                FILE *wf = fopen(wf_path, "a");
                if (wf) { fprintf(wf, "polygon=%s\n", poly_buf); fclose(wf); }
                printf("  Polygon salvo: %s\n\n", poly_buf);
            }
        }
            }
        }
    }
    if (!polm_addr || strlen(polm_addr) < 10) {
        fprintf(stderr, "Erro: carteira invalida\n"); return 1;
    }

    signal(SIGINT,  sig_handler);
    signal(SIGTERM, sig_handler);

    /* Calibrar TSC para medição precisa */
    calibrate_tsc();

    /* Calibrar TSC para medição precisa */
    calibrate_tsc();

    printf("\n====================================================\n");
    printf("  PoLM Miner C v%s — Proof of Real Memory\n", VERSION);
    printf("  PoSMA: %d steps · %d byte stride · no latency spoofing\n",
           POSMA_STEPS, POSMA_STRIDE);
    printf("====================================================\n");
    printf("  POLM:   %s\n", polm_addr);
    printf("  Node:   %s\n", node_url);
    printf("  DAG:    %dMB\n", DAG_SIZE_MB);
    printf("  Stride: %d bytes (cache miss garantido)\n\n", POSMA_STRIDE);

    /* Alocar DAG 256MB — tentar Huge Pages primeiro */
#ifdef MAP_HUGETLB
    dag = (uint8_t *)mmap(NULL, DAG_SIZE_BYTES, PROT_READ | PROT_WRITE,
                          MAP_PRIVATE | MAP_ANONYMOUS | MAP_HUGETLB, -1, 0);
    if (dag == MAP_FAILED) {
        printf("  Huge Pages: indisponivel (usando RAM padrao — latencia pode ser 10-15ns maior)\n");
        dag = (uint8_t *)malloc(DAG_SIZE_BYTES);
        if (!dag) { fprintf(stderr, "ERROR: sem memoria suficiente (precisa 256MB livres)\n"); return 1; }
    } else {
        printf("  Huge Pages: ativado (TLB otimizado)\n");
    }
#else
    dag = (uint8_t *)malloc(DAG_SIZE_BYTES);
    if (!dag) { fprintf(stderr, "ERROR: OOM\n"); return 1; }
#endif

    curl_global_init(CURL_GLOBAL_ALL);
    srand((unsigned)time(NULL));

    int    total_blocks  = 0;
    double total_earned  = 0.0;
    time_t last_submitted = 0;  /* último submit (aceito ou não) */
    char   prev_hash[65] = {0};

    /* Inicializa eviction buffer 32MB para anti-prefetch nivel 4 */
    posma_init_evict_buffer();

    while (running) {
        /* ── Buscar trabalho ── */
        char getwork_url[512];
        snprintf(getwork_url, sizeof(getwork_url),
                 "%s/getwork?miner=%s", node_url, polm_addr);

        char *work = http_get(getwork_url);
        if (!work) {
            fprintf(stderr, "  [WARN] Node offline, retry in 5s...\n");
            sleep(5); continue;
        }

        int    height     = json_int(work,    "height");
        int    difficulty = json_int(work,    "difficulty");
        double reward     = json_double(work, "reward");
        int    epoch      = json_int(work,    "epoch");
        char   new_prev[65], dag_seed[128];
        json_str(work, "prev_hash", new_prev, sizeof(new_prev));
        free(work);

        /* Salt por bloco: epoch + height — impede pré-cálculo */
        char epoch_salt[64];
        int epoch_id = height / 100000;
        char _prev16[17]; strncpy(_prev16, new_prev, 16); _prev16[16] = '\0';
        snprintf(epoch_salt, sizeof(epoch_salt), "epoch_%d_%s", epoch_id, _prev16);

        /* Seed do DAG: mesma lógica do Python */
        snprintf(dag_seed, sizeof(dag_seed), "polm:%d:%.32s", epoch, new_prev);

        /* Rebuild DAG se chain moveu */
        char dag_key[256];
        snprintf(dag_key, sizeof(dag_key), "%s:%s", dag_seed, epoch_salt);
        if (strcmp(dag_key, current_dag_key) != 0) {
            strncpy(current_dag_key, dag_key, sizeof(current_dag_key)-1);
            strncpy(prev_hash, new_prev, 64);
            printf("  Building DAG (seed: %.20s... salt: %s)  ",
                   dag_seed, epoch_salt);
            fflush(stdout);
            posma_generate_dag(dag, dag_seed, epoch_salt);
            printf("done\n");
        }

        time_t now = time(NULL); /* Delta-T removido */

        printf("  Mining #%d  diff=%d  reward=%.2f POLM\n",
               height, difficulty, reward);

        /* ── Loop de mineração ── */
        uint64_t nonce = (uint64_t)NONCE_MIN + (uint64_t)rand() % 100000;
        int chain_moved = 0;
        long checks = 0;

        while (running && !chain_moved) {
            nonce++;
            checks++;

            /* Calcular caminho PoSMA */
            PosmaResult result;
            posma_calculate_path(dag, nonce, epoch_salt, &result);

            /* Gerar hash final */
            posma_final_hash(nonce, epoch_salt, dag_seed,
                             result.merge_value, result.hash_final);

            /* Verificar dificuldade */
            if (posma_meets_target(result.hash_final, difficulty)) {
                /* Latência DRAM pura via pointer-chasing */
                /* DAG já está "quente" pelo PoSMA — mede acesso real à DRAM */
                double avg_latency_ns = polm_measure_dram_ns(nonce);

                printf("  Block found! nonce=%llu hash=%.16s... lat=%.1fns\n",
                       (unsigned long long)nonce, result.hash_final, avg_latency_ns);
                printf("  Merge[0:8]: %02x%02x%02x%02x%02x%02x%02x%02x\n",
                       result.merge_value[0], result.merge_value[1],
                       result.merge_value[2], result.merge_value[3],
                       result.merge_value[4], result.merge_value[5],
                       result.merge_value[6], result.merge_value[7]);

                /* Encode merge_value como hex para JSON */
                char *merge_hex = malloc(MERGE_VALUE_BYTES * 2 + 1);
                merge_to_hex(result.merge_value, merge_hex);

                /* Detectar CPU */
                char cpu_name_buf[128];
                get_cpu_name(cpu_name_buf, sizeof(cpu_name_buf));

                /* Montar JSON v2 com CPU e latência */
                char *submit_json = malloc(MERGE_VALUE_BYTES * 2 + 2048);
                snprintf(submit_json, MERGE_VALUE_BYTES * 2 + 2048,
                    "{"
                    "\"version\":2,"
                    "\"height\":%d,"
                    "\"prev_hash\":\"%s\","
                    "\"hash_final\":\"%s\","
                    "\"miner_id\":\"%s\","
                    "\"nonce\":%llu,"
                    "\"epoch\":%d,"
                    "\"epoch_salt\":\"%s\","
                    "\"difficulty\":%d,"
                    "\"reward\":%.2f,"
                    "\"timestamp\":%ld,"
                    "\"merge_value\":\"%s\","
                    "\"ram_type\":\"DDR4\","
                    "\"threads\":1,"
                    "\"cpu_name\":\"%s\","
                    "\"avg_latency_ns\":%.2f"
                    "}",
                    height, prev_hash, result.hash_final,
                    polm_addr, (unsigned long long)nonce,
                    epoch, epoch_salt, difficulty, reward,
                    (long)time(NULL), merge_hex,
                    cpu_name_buf, avg_latency_ns);

                /* Submeter ao endpoint v2 */
                char submit_url[512];
                snprintf(submit_url, sizeof(submit_url), "%s/submit", node_url);

                char *resp = http_post(submit_url, submit_json);
                if (resp) {
                    if (strstr(resp, "\"accepted\": true") || strstr(resp, "\"accepted\":true")) {
                        total_blocks++;
                        total_earned += reward;
                        last_submitted = time(NULL);
                        printf("  ACCEPTED! Blocks=%d Earned=%.1f POLM\n",
                               total_blocks, total_earned);
                    } else {
                        last_submitted = time(NULL);
                        printf("  Rejected: %.200s\n", resp);
                    }
                    free(resp);
                } else {
                    printf("  Submit failed (node offline)\n");
                }

                free(merge_hex);
                free(submit_json);
                chain_moved = 1;
            }

            /* Checar chain a cada 200 nonces */
            if (checks % 200 == 0) {
                char *check = http_get(getwork_url);
                if (check) {
                    char check_prev[65];
                    json_str(check, "prev_hash", check_prev, sizeof(check_prev));
                    if (strcmp(check_prev, prev_hash) != 0) {
                        printf("  Chain moved — discarding\n");
                        chain_moved = 1;
                    }
                    free(check);
                }
            }
        }
    }

    printf("\n  Stopped. Total: %d blocks, %.1f POLM\n",
           total_blocks, total_earned);
    curl_global_cleanup();
    return 0;
}
