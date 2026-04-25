@echo off
echo PoLM Miner - Windows Build Script
echo Requires: MinGW-w64, libcurl, OpenSSL for Windows
echo.
echo Install dependencies:
echo   1. Download MinGW-w64: https://winlibs.com
echo   2. Download libcurl Windows: https://curl.se/windows
echo   3. Download OpenSSL Windows: https://slproweb.com/products/Win32OpenSSL.html
echo.

set CC=gcc
set CURL_DIR=C:\curl
set SSL_DIR=C:\OpenSSL-Win64

%CC% -O2 -o polm_miner.exe ^
    miner_src\polm_miner_v2.c ^
    core\polm_core.c ^
    core\blake3\libblake3.a ^
    -Icore -Icore\blake3 ^
    -I%CURL_DIR%\include ^
    -I%SSL_DIR%\include ^
    -L%CURL_DIR%\lib ^
    -L%SSL_DIR%\lib ^
    -lcurl -lssl -lcrypto ^
    -lws2_32 -lwinmm -lm ^
    -DWIN32

if %ERRORLEVEL% == 0 (
    echo Build OK: polm_miner.exe
) else (
    echo Build FAILED
)
