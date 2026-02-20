#!/bin/bash
# =================================================================
# CANDYLAND OS: The Developer's Atomic Repair & Orchestration Kit
# Logic: Forensic Scrub + Atomic Reconstruction + Path Fix
# =================================================================

PINK='\033[38;5;205m'
BLUE='\033[38;5;81m'
MINT='\033[38;5;121m'
GOLD='\033[38;5;220m'
RESET='\033[0m'

echo -e "${PINK}🍭 INITIATING CANDYLAND OS REPAIR TOOL...${RESET}"

# 1. THE DEEP SCRUB
echo -e "${BLUE}[🧹] Purging corrupted artifacts (node_modules, .nuxt)...${RESET}"
rm -rf node_modules .nuxt package-lock.json

# 2. THE RECONSTRUCTION (Verified Recipe)
echo -e "${MINT}[📝] Writing verified package.json blueprint...${RESET}"
cat <<JSON > package.json
{
  "name": "candyland-vessel",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "nuxt build",
    "dev": "nuxt dev",
    "generate": "nuxt generate",
    "preview": "nuxt preview",
    "postinstall": "nuxt prepare"
  },
  "dependencies": {
    "nuxt": "latest",
    "vue": "latest",
    "vue-router": "latest",
    "@formkit/auto-animate": "^0.9.0"
  },
  "devDependencies": {
    "@nuxt/kit": "latest"
  },
  "overrides": {
    "minimatch": "^9.0.3"
  }
}
JSON

# 3. THE INSTALL
echo -e "${GOLD}[🛠️] Rebuilding dependency tree via NPM...${RESET}"
npm install

# 4. THE VALIDATION
if [ -f "./node_modules/.bin/nuxi" ]; then
    echo -e "${MINT}[✅] REPAIR COMPLETE: Engine block secure.${RESET}"
    echo -e "${BLUE}[🚀] Starting Local Dev Server...${RESET}"
    ./node_modules/.bin/nuxi dev
else
    echo -e "\033[31m[❌] FATAL: Installation failed. Check your network/disk space.${RESET}"
    exit 1
fi