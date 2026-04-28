CC      = gcc
CFLAGS  = -O2 -Wall
BLAKE3  = core/blake3/libblake3.a
ICORE   = -Icore -Icore/blake3

# Lib estática — Single Source of Truth
libpolmcore.a: core/polm_core.c core/polm_core.h
	$(CC) $(CFLAGS) $(ICORE) -c core/polm_core.c -o core/polm_core.o
	ar rcs libpolmcore.a core/polm_core.o

# Miner
miner: libpolmcore.a miner_src/polm_miner_v2.c
	$(CC) $(CFLAGS) $(ICORE) -o miner/polm_miner_v2 \
		miner_src/polm_miner_v2.c \
		libpolmcore.a $(BLAKE3) \
		-lpthread -lm -lssl -lcrypto -lcurl

# libposma.so para o Oracle no VPS
libposma.so: libpolmcore.a
	$(CC) $(CFLAGS) $(ICORE) -shared -fPIC -o libposma.so \
		core/polm_core.c $(BLAKE3)

clean:
	rm -f core/polm_core.o libpolmcore.a libposma.so miner/polm_miner_v2

.PHONY: miner libposma.so clean
