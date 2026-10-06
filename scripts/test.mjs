import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseVersionTag, evaluateVersionBump } from './check-version.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT_DIR = path.resolve(__dirname, '..');

let failures = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ [FAIL] ${message}`);
    failures++;
  } else {
    console.log(`✅ [PASS] ${message}`);
  }
}

console.log('==================================================================');
console.log('Running chore-media-player Automated Validation Tests');
console.log('==================================================================');

// Test 1: Essential application files exist
const requiredFiles = [
  'main.py',
  'run_player.sh',
  'smb-player.sh',
  'smb_mount.sh',
  'smb.gptk',
  'input.conf',
  'config.example.json'
];

for (const file of requiredFiles) {
  assert(fs.existsSync(path.join(ROOT_DIR, file)), `Required file '${file}' exists`);
}

// Test 2: Sensitive config verification
const exampleConfigPath = path.join(ROOT_DIR, 'config.example.json');
if (fs.existsSync(exampleConfigPath)) {
  const cfg = JSON.parse(fs.readFileSync(exampleConfigPath, 'utf8'));
  assert(cfg.smb_user === 'username' && cfg.smb_pass === 'password', 'config.example.json uses dummy credentials placeholder');
}

// Test 3: .gitignore includes private config and cache
const gitignorePath = path.join(ROOT_DIR, '.gitignore');
assert(fs.existsSync(gitignorePath), '.gitignore exists');
if (fs.existsSync(gitignorePath)) {
  const gitignore = fs.readFileSync(gitignorePath, 'utf8');
  assert(gitignore.includes('config.json'), '.gitignore excludes config.json');
  assert(gitignore.includes('dist/'), '.gitignore excludes dist/');
}

// Test 4: GEMINI.md Project Rules Exist
const geminiMdPath = path.join(ROOT_DIR, 'GEMINI.md');
assert(fs.existsSync(geminiMdPath), 'GEMINI.md project rules file exists');
if (fs.existsSync(geminiMdPath)) {
  const geminiContent = fs.readFileSync(geminiMdPath, 'utf8');
  assert(geminiContent.includes('Major.Minor.Patch.Revision'), 'GEMINI.md defines 4-part version rule');
  assert(geminiContent.includes('pnpm'), 'GEMINI.md defines pnpm package manager rule');
}

// Test 5: package.json follows 4-part semantic versioning
const pkgPath = path.join(ROOT_DIR, 'package.json');
const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf8'));
const versionParts = pkg.version.split('.');
assert(versionParts.length === 4, `package.json version (${pkg.version}) uses 4-part Major.Minor.Patch.Revision format`);

// Test 6: Version Checker Unit Tests (evaluateVersionBump)
console.log('--- Version Bump Qualification Tests ---');

// Case A: Initial minor bump (patch=0, revision=0)
const resMinor = evaluateVersionBump('v0.1.0.0', []);
assert(resMinor.shouldBuild === true, 'Minor bump (v0.1.0.0) qualifies for build');

// Case B: Major bump
const resMajor = evaluateVersionBump('v1.0.0.0', []);
assert(resMajor.shouldBuild === true, 'Major bump (v1.0.0.0) qualifies for build');

// Case C: Patch bump (patch=1, revision=0)
const resPatch = evaluateVersionBump('v0.1.1.0', []);
assert(resPatch.shouldBuild === false, 'Patch bump (v0.1.1.0) is correctly skipped');

// Case D: Revision bump (patch=0, revision=1)
const resRev = evaluateVersionBump('v0.1.0.1', []);
assert(resRev.shouldBuild === false, 'Revision bump (v0.1.0.1) is correctly skipped');

console.log('------------------------------------------------------------------');
if (failures > 0) {
  console.error(`Test run failed with ${failures} error(s).`);
  process.exit(1);
} else {
  console.log('All automated validation tests passed!');
  process.exit(0);
}
