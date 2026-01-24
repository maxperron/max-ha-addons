#!/usr/bin/with-contenv bashio

echo "--- Gemini Station Starting ---"

# Ensure persistence directory exists
if [ ! -d /data/.gemini ]; then
    echo "Creating persistent directory at /data/.gemini"
    mkdir -p /data/.gemini
fi

# Create symlink for persistence
# This ensures that when the user authenticates with 'gemini login',
# the credentials stored in /root/.gemini are actually saved to /data/.gemini
echo "Linking /root/.gemini to /data/.gemini"
rm -rf /root/.gemini
ln -s /data/.gemini /root/.gemini

echo "Starting ttyd on port 8099..."
# -W enables writing (interactive terminal)
exec ttyd -p 8099 -W bash
