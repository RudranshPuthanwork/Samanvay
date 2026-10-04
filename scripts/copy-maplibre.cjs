const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, '..', 'node_modules', 'maplibre-gl', 'dist');
const targets = [
  path.join(__dirname, '..', 'public'),
  path.join(__dirname, '..', 'public', 'assets'),
  path.join(__dirname, '..', 'dist'),
  path.join(__dirname, '..', 'dist', 'assets'),
];

for (const target of targets) {
  fs.mkdirSync(target, { recursive: true });
}

for (const file of fs.readdirSync(srcDir)) {
  const src = path.join(srcDir, file);
  if (fs.statSync(src).isFile()) {
    for (const target of targets) {
      fs.copyFileSync(src, path.join(target, file));
    }
  }
}

console.log('Successfully copied MapLibre dist assets to all public and dist target directories');
