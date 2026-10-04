import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

const BANNED_PACKAGES = [
  'lucide-react',
  'react-icons',
  '@heroicons',
  '@phosphor-icons',
  '@tabler',
  '@radix-ui/react-icons',
  'font-awesome',
  '@fortawesome',
];

const BANNED_WORDS = [
  'seamless',
  'seamlessly',
  'elevate',
  'unlock',
  'unleash',
  'empower',
  'supercharge',
  'revolutionary',
  'revolutionize',
  'next-gen',
  'cutting-edge',
  'state-of-the-art',
  'game-changing',
  'effortless',
  'intuitive',
  'robust',
  'leverage',
  'delve',
  'harness',
  'streamline',
  'powered by ai',
  'ai-powered',
  'smart',
  'insights',
  'dashboard',
  'mission control center',
  'command center',
  'welcome',
  'get started',
  'lorem',
  'placeholder',
  'coming soon',
  'oops',
  'something went wrong',
];

const BANNED_SCAFFOLD = [
  'vite.svg',
  'react.svg',
  'Vite + React',
  'App.css',
];

const BANNED_TAILWIND_PALETTES = [
  'slate-',
  'zinc-',
  'gray-',
  'neutral-',
  'stone-',
  'red-',
  'orange-',
  'amber-',
  'yellow-',
  'lime-',
  'green-',
  'emerald-',
  'teal-',
  'cyan-',
  'sky-',
  'blue-',
  'indigo-',
  'violet-',
  'purple-',
  'fuchsia-',
  'pink-',
  'rose-',
];

// Helper to convert hex to HSL
function hexToHsl(hexStr) {
  let hex = hexStr.replace('#', '');
  if (hex.length === 3) {
    hex = hex.split('').map(c => c + c).join('');
  }
  if (hex.length !== 6 && hex.length !== 8) return null;

  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0);
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      case b:
        h = (r - g) / d + 4;
        break;
    }
    h *= 60;
  }

  return { h, s: s * 100, l: l * 100 };
}

// Emoji regex
const EMOJI_REGEX = /\p{Extended_Pictographic}/u;

function collectFiles(dir, extensions, ignoreDirs = ['node_modules', 'dist', '.git', '.venv']) {
  let results = [];
  if (!fs.existsSync(dir)) return results;
  const list = fs.readdirSync(dir);
  for (const file of list) {
    if (ignoreDirs.includes(file)) continue;
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      results = results.concat(collectFiles(fullPath, extensions, ignoreDirs));
    } else {
      const ext = path.extname(fullPath).toLowerCase();
      if (extensions.includes(ext)) {
        results.push(fullPath);
      }
    }
  }
  return results;
}

let violations = [];

function addViolation(file, lineNum, rule, snippet) {
  const relFile = path.relative(rootDir, file).replace(/\\/g, '/');
  violations.push({ file: relFile, lineNum, rule, snippet: snippet.trim() });
}

// 1. Scan src/** and index.html
const allFilesToScan = [
  path.join(rootDir, 'index.html'),
  ...collectFiles(path.join(rootDir, 'src'), ['.ts', '.tsx', '.js', '.jsx', '.css', '.html']),
];

for (const file of allFilesToScan) {
  if (!fs.existsSync(file)) continue;
  const content = fs.readFileSync(file, 'utf-8');
  const lines = content.split('\n');
  const isChartFile = /chart/i.test(path.basename(file));

  for (let idx = 0; idx < lines.length; idx++) {
    const line = lines[idx];
    const lineNum = idx + 1;

    // Check imports
    for (const pkg of BANNED_PACKAGES) {
      if (line.includes(`from '${pkg}`) || line.includes(`from "${pkg}`) || line.includes(`import '${pkg}`) || line.includes(`import "${pkg}`)) {
        addViolation(file, lineNum, `Banned icon/package import: ${pkg}`, line);
      }
    }

    // Check border-radius / rounded
    if (line.includes('border-radius') && !line.includes('border-radius: 0') && !line.includes('border-radius:0')) {
      addViolation(file, lineNum, 'border-radius must be 0', line);
    }
    const roundedMatch = line.match(/\brounded(-[\w[\]]+)?\b/);
    if (roundedMatch) {
      // Allow rounded-none
      if (roundedMatch[0] !== 'rounded-none') {
        addViolation(file, lineNum, `Banned rounded corner class/style: ${roundedMatch[0]}`, line);
      }
    }

    // Strip Tailwind internal CSS variables (--tw-*) before checking classes/properties
    const cleanLine = line.replace(/--tw-[\w-]+/g, '');

    // Check box-shadow / drop-shadow / backdrop-filter / blur
    if (/(?<![\w-])box-shadow\s*:/.test(cleanLine) && !cleanLine.includes('box-shadow: none') && !cleanLine.includes('box-shadow:none') && !cleanLine.includes('box-shadow: 0') && !cleanLine.includes('box-shadow:0')) {
      addViolation(file, lineNum, 'box-shadow must be none', line);
    }
    if (/(?<![\w-])shadow(?!-none\b)(-[\w[\]]+)?\b/.test(cleanLine)) {
      addViolation(file, lineNum, 'Banned Tailwind shadow class', line);
    }
    if (cleanLine.includes('drop-shadow')) {
      addViolation(file, lineNum, 'Banned drop-shadow', line);
    }
    if (cleanLine.includes('backdrop-filter') || cleanLine.includes('backdrop-blur') || /\bblur\(/.test(cleanLine)) {
      addViolation(file, lineNum, 'Banned backdrop-filter or blur', line);
    }

    // Check gradients
    if (cleanLine.includes('gradient(') || cleanLine.includes('linear-gradient') || cleanLine.includes('radial-gradient') || /\bbg-gradient-/.test(cleanLine)) {
      addViolation(file, lineNum, 'Banned gradient', line);
    }

    // Check animations / transitions
    if (cleanLine.includes('transition: all') || cleanLine.includes('transition-all')) {
      addViolation(file, lineNum, 'Banned transition: all / transition-all', line);
    }
    if (/\banimate-pulse\b|\banimate-bounce\b|\banimate-ping\b|\bhover:scale\b|\btranslate-y\b/.test(cleanLine)) {
      addViolation(file, lineNum, 'Banned motion effect/animation', line);
    }

    // Check uppercase text transform / wide tracking (Spec §6.7 & Section B3)
    if (cleanLine.includes('text-transform: uppercase') || /\buppercase\b/.test(cleanLine)) {
      addViolation(file, lineNum, 'Banned uppercase (use sentence case for section labels)', line);
    }
    if (/\btracking-wider\b|\btracking-widest\b/.test(cleanLine)) {
      addViolation(file, lineNum, 'Banned wide tracking (letter-spacing must be 0 to 0.01em)', line);
    }
    const lsMatch = cleanLine.match(/letter-spacing:\s*([0-9.]+)(em|px)/);
    if (lsMatch) {
      const val = parseFloat(lsMatch[1]);
      const unit = lsMatch[2];
      if ((unit === 'em' && val > 0.01) || (unit === 'px' && val > 0.16)) {
        addViolation(file, lineNum, 'Banned letter-spacing above 0.01em', line);
      }
    }

    // Check edge glow or vignette (Section B3)
    if (cleanLine.includes('vignette') || cleanLine.includes('edge-glow') || /\b(glow|blue-glow)\b/.test(cleanLine)) {
      addViolation(file, lineNum, 'Banned glow/vignette effect', line);
    }

    // Check banned Tailwind palettes
    for (const pal of BANNED_TAILWIND_PALETTES) {
      // Matches e.g. text-slate-500, bg-zinc-800, border-indigo-500
      const palRegex = new RegExp(`\\b(bg|text|border|fill|stroke|ring)-${pal}\\d+\\b`);
      if (palRegex.test(line)) {
        addViolation(file, lineNum, `Banned default Tailwind palette class: ${pal}`, line);
      }
    }

    // Check hex colors
    const hexMatches = line.match(/#[0-9a-fA-F]{3,8}\b/g);
    if (hexMatches) {
      for (const hex of hexMatches) {
        const hsl = hexToHsl(hex);
        if (hsl) {
          // Rule 1: Hue 250°-330° at Saturation > 15% (indigo, violet, purple, fuchsia)
          if (hsl.h >= 250 && hsl.h <= 330 && hsl.s > 15) {
            addViolation(file, lineNum, `Banned color (hue in 250°-330° band): ${hex} (h:${Math.round(hsl.h)}, s:${Math.round(hsl.s)}%)`, line);
          }
          // Rule 2: Neon band (sat > 85%, lightness 45-65%)
          if (hsl.s > 85 && hsl.l >= 45 && hsl.l <= 65) {
            addViolation(file, lineNum, `Banned neon color (saturation > 85% & lightness 45-65%): ${hex}`, line);
          }
        }
      }
    }

    // Check emoji (allow legitimate copyright symbol © mandated by OpenStreetMap license)
    const lineWithoutCopyright = line.replace(/©/g, '');
    if (EMOJI_REGEX.test(lineWithoutCopyright)) {
      addViolation(file, lineNum, 'Banned emoji character', line);
    }

    // Check raw <svg> elements outside allowed chart context
    if (/<svg\b/i.test(line) && !isChartFile && !line.includes('/* allow-svg: chart */')) {
      addViolation(file, lineNum, 'Banned raw <svg> in non-chart component', line);
    }

    // Check banned font families
    const fontMatches = line.match(/font-family:\s*([^;]+)/i);
    if (fontMatches) {
      const familyStr = fontMatches[1];
      const allowed = ['IBM Plex Sans', 'IBM Plex Mono', 'IBM Plex Sans Devanagari', 'monospace', 'sans-serif', 'inherit'];
      const hasAllowed = allowed.some(a => familyStr.includes(a));
      if (!hasAllowed) {
        addViolation(file, lineNum, `Banned font family: ${familyStr}`, line);
      }
    }

    // Check em dashes
    if (line.includes('—') || line.includes('\u2014')) {
      addViolation(file, lineNum, 'Banned em dash (use real glyphs/sentence structure without em dashes)', line);
    }

    // Check banned scaffold items
    for (const scaf of BANNED_SCAFFOLD) {
      if (line.includes(scaf)) {
        addViolation(file, lineNum, `Banned scaffold item: ${scaf}`, line);
      }
    }

    // Check banned words in UI files (case insensitive, whole word/phrase; exclude stylesheets)
    if (!file.endsWith('.css')) {
      const lowerLine = line.toLowerCase();
      for (const word of BANNED_WORDS) {
        // Regex with word boundaries
        const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const wordRegex = new RegExp(`\\b${escaped}\\b`, 'i');
        if (wordRegex.test(lowerLine)) {
          // Exclude comments that reference the ban list itself
          if (!lowerLine.includes('banned') && !lowerLine.includes('anti-vibe')) {
            addViolation(file, lineNum, `Banned word: "${word}"`, line);
          }
        }
      }
    }
  }
}

if (violations.length > 0) {
  console.error(`\x1b[31m[check:design] FAILED with ${violations.length} violation(s):\x1b[0m\n`);
  for (const v of violations) {
    console.error(`  \x1b[33m${v.file}:${v.lineNum}\x1b[0m: ${v.rule}`);
    console.error(`    \x1b[90m${v.snippet.slice(0, 120)}...\x1b[0m\n`);
  }
  process.exit(1);
} else {
  console.log('\x1b[32m[check:design] PASSED: No design/slop violations found.\x1b[0m');
  process.exit(0);
}
