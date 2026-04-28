#ifndef POLM_CRYPTO_COMPAT_H
#define POLM_CRYPTO_COMPAT_H
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

/* SHA-256 */
typedef struct { uint32_t state[8]; uint64_t count; uint8_t buf[64]; } SHA256_CTX;
static const uint32_t _K256[64]={0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
#define ROR32(x,n)(((x)>>(n))|((x)<<(32-(n))))
#define CH(x,y,z)(((x)&(y))^(~(x)&(z)))
#define MAJ(x,y,z)(((x)&(y))^((x)&(z))^((y)&(z)))
#define S0(x)(ROR32(x,2)^ROR32(x,13)^ROR32(x,22))
#define S1(x)(ROR32(x,6)^ROR32(x,11)^ROR32(x,25))
#define R0(x)(ROR32(x,7)^ROR32(x,18)^((x)>>3))
#define R1(x)(ROR32(x,17)^ROR32(x,19)^((x)>>10))
static void _sha256_transform(uint32_t s[8],const uint8_t*b){uint32_t w[64],t1,t2;int i;for(i=0;i<16;i++)w[i]=((uint32_t)b[i*4]<<24)|((uint32_t)b[i*4+1]<<16)|((uint32_t)b[i*4+2]<<8)|b[i*4+3];for(i=16;i<64;i++)w[i]=R1(w[i-2])+w[i-7]+R0(w[i-15])+w[i-16];uint32_t a=s[0],b2=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];for(i=0;i<64;i++){t1=h+S1(e)+CH(e,f,g)+_K256[i]+w[i];t2=S0(a)+MAJ(a,b2,c);h=g;g=f;f=e;e=d+t1;d=c;c=b2;b2=a;a=t1+t2;}s[0]+=a;s[1]+=b2;s[2]+=c;s[3]+=d;s[4]+=e;s[5]+=f;s[6]+=g;s[7]+=h;}
static void SHA256_Init(SHA256_CTX*c){c->state[0]=0x6a09e667;c->state[1]=0xbb67ae85;c->state[2]=0x3c6ef372;c->state[3]=0xa54ff53a;c->state[4]=0x510e527f;c->state[5]=0x9b05688c;c->state[6]=0x1f83d9ab;c->state[7]=0x5be0cd19;c->count=0;}
static void SHA256_Update(SHA256_CTX*c,const void*data,size_t len){const uint8_t*p=data;size_t r=c->count%64;c->count+=len;if(r){size_t n=64-r;if(n>len)n=len;memcpy(c->buf+r,p,n);p+=n;len-=n;r+=n;if(r==64){_sha256_transform(c->state,c->buf);}}while(len>=64){_sha256_transform(c->state,p);p+=64;len-=64;}if(len)memcpy(c->buf,p,len);}
static void SHA256_Final(uint8_t*digest,SHA256_CTX*c){uint8_t pad[64]={0};uint64_t bits=c->count*8;size_t r=c->count%64;pad[0]=0x80;size_t plen=(r<56)?56-r:120-r;SHA256_Update(c,pad,plen);uint8_t lb[8];for(int i=7;i>=0;i--){lb[i]=bits&0xff;bits>>=8;}SHA256_Update(c,lb,8);for(int i=0;i<8;i++){digest[i*4]=c->state[i]>>24;digest[i*4+1]=c->state[i]>>16;digest[i*4+2]=c->state[i]>>8;digest[i*4+3]=c->state[i];}}

/* SHA3-256 (Keccak) */
typedef struct{uint64_t s[25];uint8_t buf[136];size_t pt;}EVP_MD_CTX;
typedef int EVP_MD;
static const uint64_t _RC[24]={0x1ULL,0x8082ULL,0x800000000000808aULL,0x8000000080008000ULL,0x808bULL,0x80000001ULL,0x8000000080008081ULL,0x8000000000008009ULL,0x8aULL,0x88ULL,0x80008009ULL,0x8000000aULL,0x8000808bULL,0x800000000000008bULL,0x8000000000008089ULL,0x8000000000008003ULL,0x8000000000008002ULL,0x8000000000000080ULL,0x800aULL,0x800000008000000aULL,0x8000000080008081ULL,0x8000000000008080ULL,0x80000001ULL,0x8000000080008008ULL};
static const int _PI[24]={10,7,11,17,18,3,5,16,8,21,24,4,15,23,19,13,12,2,20,14,22,9,6,1};
static const int _RHO[24]={1,3,6,10,15,21,28,36,45,55,2,14,27,41,56,8,25,43,62,18,39,61,20,44};
#define ROT64(x,n)(((x)<<(n))|((x)>>(64-(n))))
static void _kf(uint64_t s[25]){for(int r=0;r<24;r++){uint64_t bc[5],t;for(int i=0;i<5;i++)bc[i]=s[i]^s[i+5]^s[i+10]^s[i+15]^s[i+20];for(int i=0;i<5;i++){t=bc[(i+4)%5]^ROT64(bc[(i+1)%5],1);for(int j=0;j<25;j+=5)s[j+i]^=t;}uint64_t last=s[1];for(int i=0;i<24;i++){int j=_PI[i];t=s[j];s[j]=ROT64(last,_RHO[i]);last=t;}for(int j=0;j<25;j+=5){for(int i=0;i<5;i++)bc[i]=s[j+i];for(int i=0;i<5;i++)s[j+i]^=~bc[(i+1)%5]&bc[(i+2)%5];}s[0]^=_RC[r];}}
static EVP_MD_CTX*EVP_MD_CTX_new(void){EVP_MD_CTX*c=calloc(1,sizeof(EVP_MD_CTX));return c;}
static void EVP_MD_CTX_free(EVP_MD_CTX*c){free(c);}
static const EVP_MD*EVP_sha3_256(void){return NULL;}
static int EVP_DigestInit_ex(EVP_MD_CTX*c,const EVP_MD*t,void*e){(void)t;(void)e;memset(c,0,sizeof(*c));return 1;}
static int EVP_DigestUpdate(EVP_MD_CTX*c,const void*d,size_t l){const uint8_t*p=d;while(l-->0){c->buf[c->pt++]=*p++;if(c->pt==136){for(size_t i=0;i<17;i++){uint64_t v=0;for(int j=7;j>=0;j--)v=(v<<8)|c->buf[i*8+j];c->s[i]^=v;}_kf(c->s);c->pt=0;}}return 1;}
static int EVP_DigestFinal_ex(EVP_MD_CTX*c,uint8_t*out,unsigned int*l){c->buf[c->pt]=0x06;memset(c->buf+c->pt+1,0,136-c->pt-1);c->buf[135]|=0x80;for(size_t i=0;i<17;i++){uint64_t v=0;for(int j=7;j>=0;j--)v=(v<<8)|c->buf[i*8+j];c->s[i]^=v;}_kf(c->s);for(int i=0;i<4;i++){uint64_t v=c->s[i];for(int j=0;j<8;j++){out[i*8+j]=v&0xff;v>>=8;}}if(l)*l=32;return 1;}
#endif

/* ── Windows helpers ──────────────────────────────────────── */
#ifdef _WIN32
#include <windows.h>
#include <bcrypt.h>

static inline const char* get_home_dir(void) {
    const char *h = getenv("USERPROFILE");
    if (!h) h = getenv("APPDATA");
    if (!h) h = ".";
    return h;
}

static inline int read_random_bytes(uint8_t *buf, size_t len) {
    return BCryptGenRandom(NULL, buf, (ULONG)len, BCRYPT_USE_SYSTEM_PREFERRED_RNG) == 0 ? 1 : 0;
}
#else
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
