#!/usr/bin/env node
/**
 * Copy Playwright snapshot images to docs/ for README embedding.
 * Run after: npm run test:e2e -- --grep screenshot
 * Or: npm run capture-screenshots (runs tests then copies)
 */
const fs = require('fs');
const path = require('path');

const snapshotDir = path.join(__dirname, '../tests/e2e/snapshots/dashboard.spec.js-snapshots');
const docsDir = path.join(__dirname, '../docs');

const copies = [
  ['dashboard-empty-chromium.png', 'dashboard-empty.png'],
  ['dashboard-with-jobs-chromium.png', 'dashboard-with-jobs.png'],
];

for (const [src, dest] of copies) {
  const srcPath = path.join(snapshotDir, src);
  const destPath = path.join(docsDir, dest);
  if (fs.existsSync(srcPath)) {
    fs.copyFileSync(srcPath, destPath);
    console.log(`Copied ${src} → docs/${dest}`);
  } else {
    console.warn(`Snapshot not found: ${srcPath} (run: npm run test:e2e -- --grep screenshot)`);
  }
}
