#!/usr/bin/env node
/**
 * Start the Catcher backend (creates venv if needed).
 * Used by: npm run backend, npm run serve
 */
const { spawn } = require('child_process');
const path = require('path');

const script = path.join(__dirname, 'run-backend.sh');
const child = spawn(script, [], {
  stdio: 'inherit',
  env: process.env,
  shell: false,
});

child.on('exit', (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 1);
});
