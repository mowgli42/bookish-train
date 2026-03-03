/**
 * Phase 1 validation: Dashboard workflow and visual capture.
 * Prerequisites: catcher on :8000, dashboard on :5173 (or BASE_URL).
 * Mock data: tests/fixtures/mock-data/ (MANIFEST.json).
 */
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

const MANIFEST_PATH = path.join(__dirname, '../fixtures/mock-data/MANIFEST.json');
const mockFiles = (() => {
  try {
    const m = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
    return m.files || [];
  } catch {
    return [];
  }
})();

test.describe('Phase 1: Dashboard', () => {
  test('health check - catcher responds', async ({ request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const r = await request.get(`${catcher}/health`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.status).toBe('ok');
  });

  test('dashboard loads and shows title', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Edge Backup Dashboard/i })).toBeVisible();
  });

  test('dashboard has main sections', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Edge Backup Dashboard/i })).toBeVisible();
    await expect(page.getByRole('region', { name: /packages/i })).toBeVisible();
  });

  test('packages section with grid visible', async ({ page }) => {
    await page.goto('/');
    const packagesSection = page.getByRole('region', { name: /packages/i });
    await expect(packagesSection).toBeVisible({ timeout: 10000 });
    await expect(packagesSection.locator('.grid-wrapper')).toBeVisible();
  });

  test('clients section visible', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /clients/i })).toBeVisible();
  });

  test('dashboard empty state - screenshot', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Edge Backup Dashboard/i })).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('region', { name: /packages/i })).toBeVisible();
    await page.waitForTimeout(500);
    await expect(page.locator('main')).toHaveScreenshot('dashboard-empty.png', {
      mask: [page.locator('time')],
    });
  });

  test('ingest rejects size_bytes>0 without checksum (OpenSpec §7)', async ({ request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const r = await request.post(`${catcher}/api/v1/ingest`, {
      data: { source_id: 'test', path: 'x', size_bytes: 1 },
    });
    expect(r.status()).toBe(422);
  });

  test('packages endpoint returns list', async ({ request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const r = await request.get(`${catcher}/api/v1/packages`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('buckets endpoint returns summary', async ({ request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const r = await request.get(`${catcher}/api/v1/buckets`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.buckets).toBeDefined();
    expect(Array.isArray(body.buckets)).toBe(true);
  });

  test('config endpoint returns retention rules', async ({ request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const r = await request.get(`${catcher}/api/v1/config`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.retention).toBeDefined();
    const stops = body.retention?.stops ?? body.rule_sets?.user_data?.stops;
    expect(stops).toBeDefined();
    expect(stops.hot).toBeDefined();
    const hotWait = stops.hot?.wait_days ?? stops.hot?.wait_seconds;
    expect(hotWait !== undefined || stops.hot?.enabled === false).toBeTruthy();
  });

  test('projections endpoint returns transitions', async ({ request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const r = await request.get(`${catcher}/api/v1/projections?days=5`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.days).toBe(5);
    expect(Array.isArray(body.transitions)).toBe(true);
  });

  test('Train page shows migration rules grid with user_data retention', async ({ page, request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const configRes = await request.get(`${catcher}/api/v1/config`);
    expect(configRes.ok()).toBeTruthy();
    const config = await configRes.json();
    const ruleSets = config.rule_sets || {};
    const userData = ruleSets.user_data || {};
    const hotStop = userData?.stops?.hot;
    const hotVal = hotStop?.enabled ? (hotStop.wait_days ?? hotStop.wait_seconds ?? 7) : 0;
    const unit = config.demo_mode ? 's' : 'd';

    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Migration rules by type/i })).toBeVisible({ timeout: 10000 });
    const grid = page.getByRole('grid', { name: /Retention rules per package type/i });
    await expect(grid).toBeVisible();
    const pattern = hotVal > 0 ? new RegExp(`${hotVal}\\s*${unit}\\s*\\(`) : /skip|0\s*d\s*\(/;
    await expect(grid.getByText(pattern).first()).toBeVisible();
  });
});

test.describe('Phase 1: Dashboard with jobs', () => {
  test('dashboard with jobs - screenshot (mock data from MANIFEST)', async ({ page, request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const sourceId = 'e2e-mock-source';
    const payloads = mockFiles.length
      ? mockFiles.map((f) => ({
          source_id: sourceId,
          path: f.path,
          checksum: f.checksum,
          size_bytes: f.size_bytes,
          tier_hint: f.tier_hint,
        }))
      : [{ source_id: sourceId, path: 'test/file.txt', checksum: 'abc123', size_bytes: 1 }];

    for (const payload of payloads) {
      const r = await request.post(`${catcher}/api/v1/ingest`, { data: payload });
      expect(r.ok(), `ingest ${payload.path}: ${r.status()}`).toBeTruthy();
    }

    await page.goto('/');
    await expect(page.getByRole('region', { name: /packages/i }).getByText(payloads[0].path).first()).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator('main')).toHaveScreenshot('dashboard-with-jobs.png', {
      mask: [page.locator('time')],
    });
  });
});
