#!/bin/bash
# Rebuilds the frontend and deploys it cleanly to Nginx's serving directory.
# Wipes old hashed assets first so index.html never references a file
# that doesn't exist on disk - the exact bug that caused a real outage.
set -euo pipefail

echo "Building..."
rm -rf dist node_modules/.vite
npm run build

echo "Deploying..."
sudo rm -rf /var/www/infrafox/assets
sudo cp -r dist/* /var/www/infrafox/
sudo chown -R www-data:www-data /var/www/infrafox

echo "Done. Deployed: $(grep -o 'assets/index-[^"]*.js' dist/index.html)"
