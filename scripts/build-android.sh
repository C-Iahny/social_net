#!/bin/bash
# Compile l'application Android Vazimba (AAB signé pour le Play Store) sur ce Mac.
#
# Prérequis (installés le 2026-10-15 dans ~/Documents/outils-android, sans droits admin) :
#   - jdk/        Temurin 21        - node/   Node 22 (npm, npx cap)
#   - sdk/        Android SDK (platform 36, build-tools 36, platform-tools)
#   - env.sh      exporte JAVA_HOME, ANDROID_HOME et le PATH
# Signature : vazimba-android/android/keystore.properties (ignoré par git) pointe vers
# le keystore conservé dans ~/Documents/vazimba-sauvegardes/keystore-android-*/.
#
# Usage :  scripts/build-android.sh            → AAB (Play Store)
#          scripts/build-android.sh apk        → APK universel signé (test direct sur un téléphone)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$HOME/Documents/outils-android"
[ -f "$TOOLS/env.sh" ] || { echo "Outils absents : $TOOLS/env.sh introuvable"; exit 1; }
# shellcheck disable=SC1090
source "$TOOLS/env.sh"
export GRADLE_USER_HOME="$TOOLS/gradle"

cd "$HERE/vazimba-android"
[ -f android/keystore.properties ] || { echo "android/keystore.properties manquant (voir keystore.properties.template)"; exit 1; }
[ -d node_modules ] || npm install --no-audit --no-fund
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > android/local.properties
npx cap sync android

cd android
chmod +x gradlew
if [ "${1:-aab}" = "apk" ]; then
    ./gradlew --no-daemon -q assembleRelease
    OUT="app/build/outputs/apk/release/app-release.apk"
else
    ./gradlew --no-daemon -q bundleRelease
    OUT="app/build/outputs/bundle/release/app-release.aab"
fi
VER=$(grep -E 'versionName' app/build.gradle | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
CODE=$(grep -E 'versionCode' app/build.gradle | head -1 | sed -E 's/.*versionCode ([0-9]+).*/\1/')
DEST="$HOME/Documents/vazimba-sauvegardes/builds"
mkdir -p "$DEST"
cp "$OUT" "$DEST/vazimba-$VER-$CODE.${OUT##*.}"
echo "✔ Fichier prêt : $DEST/vazimba-$VER-$CODE.${OUT##*.}  (version $VER, code $CODE)"
