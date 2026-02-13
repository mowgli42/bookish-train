/** @type {import('@playwright/test').PlaywrightTestConfig} */
const config = {
  testDir: './tests/e2e',
  outputDir: './tests/e2e/test-results',
  snapshotDir: './tests/e2e/snapshots',
  snapshotPathTemplate: '{snapshotDir}/{testFileDir}/{testFileName}-snapshots/{arg}-{projectName}{ext}',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [['html', { outputFolder: './tests/e2e/playwright-report' }], ['list']],
  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
  },
  projects: [{
    name: 'chromium',
    use: {
      channel: 'chromium',
      viewport: { width: 1280, height: 720 },
    },
  }],
  timeout: 20000,
  expect: {
    toHaveScreenshot: { maxDiffPixelRatio: 0.02 },
  },
  webServer: [
    {
      command: 'python3 -m uvicorn main:app --port 8000 --host 127.0.0.1',
      cwd: './backend',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: true,
      timeout: 60000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1',
      cwd: './frontend',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 60000,
    },
  ],
};

module.exports = config;
