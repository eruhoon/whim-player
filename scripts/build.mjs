import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');
const DIST_DIR = path.join(ROOT_DIR, 'dist');

const pkgPath = path.join(ROOT_DIR, 'package.json');
const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));

function copyRecursiveSync(src, dest) {
  const exists = fs.existsSync(src);
  const stats = exists && fs.statSync(src);
  const isDirectory = exists && stats.isDirectory();
  if (isDirectory) {
    fs.mkdirSync(dest, { recursive: true });
    fs.readdirSync(src).forEach((childItemName) => {
      copyRecursiveSync(path.join(src, childItemName), path.join(dest, childItemName));
    });
  } else {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
  }
}

console.log('==================================================================');
console.log(`Building SMB Media Player for ROCKNIX (v${pkg.version})`);
console.log('==================================================================');

// 1. Clean dist directory
if (fs.existsSync(DIST_DIR)) {
  console.log('[1/5] Cleaning existing dist directory...');
  fs.rmSync(DIST_DIR, { recursive: true, force: true });
}
fs.mkdirSync(DIST_DIR, { recursive: true });

// 2. Prepare ports structure
// ROCKNIX Ports structure:
// /storage/roms/ports/
// ├── SMB Media Player.sh
// └── smb-player/
//     ├── main.py
//     ├── run_player.sh
//     ├── smb_mount.sh
//     ├── input.conf
//     ├── smb.gptk
//     └── config.json (from config.example.json or config.json)
console.log('[2/5] Assembling ports folder structure...');
const distPortsDir = path.join(DIST_DIR, 'ports');
const distAppDir = path.join(distPortsDir, 'smb-player');
fs.mkdirSync(distAppDir, { recursive: true });

// Copy root launcher script
fs.copyFileSync(path.join(ROOT_DIR, 'smb-player.sh'), path.join(distPortsDir, 'SMB Media Player.sh'));
fs.chmodSync(path.join(distPortsDir, 'SMB Media Player.sh'), 0o755);

// Copy application files
const appFiles = [
  'main.py',
  'run_player.sh',
  'smb_mount.sh',
  'input.conf',
  'smb.gptk'
];

for (const file of appFiles) {
  const src = path.join(ROOT_DIR, file);
  const dest = path.join(distAppDir, file);
  fs.copyFileSync(src, dest);
  if (file.endsWith('.sh') || file.endsWith('.py')) {
    fs.chmodSync(dest, 0o755);
  }
}

// Config file: use config.example.json as base template
fs.copyFileSync(
  path.join(ROOT_DIR, 'config.example.json'),
  path.join(distAppDir, 'config.json')
);

// 3. Copy documentation into dist
console.log('[3/5] Copying documentation and README...');
if (fs.existsSync(path.join(ROOT_DIR, 'README.md'))) {
  fs.copyFileSync(path.join(ROOT_DIR, 'README.md'), path.join(distPortsDir, 'README.md'));
}

// 4. Create release archives
console.log('[4/5] Creating release distribution zip archives...');
const releaseZipName = `smb-player-rocknix-v${pkg.version}.zip`;
const genericZipName = 'smb-player-rocknix.zip';
const releaseZipPath = path.join(DIST_DIR, releaseZipName);
const genericZipPath = path.join(DIST_DIR, genericZipName);

try {
  // Zip the contents inside ports/ directory
  const zipCmd = `zip -r -q "${releaseZipName}" .`;
  execSync(zipCmd, { cwd: distPortsDir, stdio: 'inherit' });
  fs.renameSync(path.join(distPortsDir, releaseZipName), releaseZipPath);
  fs.copyFileSync(releaseZipPath, genericZipPath);

  const stats = fs.statSync(releaseZipPath);
  console.log(`  • Created ${releaseZipName} (${(stats.size / 1024).toFixed(1)} KB)`);
  console.log(`  • Created ${genericZipName} (${(stats.size / 1024).toFixed(1)} KB)`);
} catch (err) {
  console.warn(`[WARN] System zip utility unavailable or failed: ${err.message}. Release zip skipped.`);
}

console.log('\n[5/5] Build Summary');
console.log('------------------------------------------------------------------');
console.log(`Artifact directory: ${distPortsDir}`);
console.log(`Release Archive:    ${releaseZipPath}`);
console.log('[SUCCESS] SMB Media Player build completed successfully!\n');
