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

async function goToPage(page, hash) {
  await page.goto(`/#${hash}`);
  await page.getByRole('link', { name: new RegExp(hash, 'i') }).first().click();
}

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
    await expect(page.getByRole('heading', { name: /Edge Backup Railway/i, level: 1 })).toBeVisible();
  });

  test('dashboard has main nav and tracks view', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('navigation', { name: /main/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Track diagram/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Migration rules by type/i })).toBeVisible();
  });

  test('packages page with grid visible', async ({ page }) => {
    await page.goto('/');
    await goToPage(page, 'packages');
    await expect(page.getByRole('heading', { name: /Package tracking/i })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('#packages .grid-wrapper')).toBeVisible();
  });

  test('clients page visible', async ({ page }) => {
    await page.goto('/');
    await goToPage(page, 'clients');
    await expect(page.getByRole('heading', { name: /^Clients$/i })).toBeVisible();
  });

  test('tracks page empty state - screenshot', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /Track diagram/i })).toBeVisible({ timeout: 10000 });
    await page.waitForTimeout(500);
    await expect(page.locator('main')).toHaveScreenshot('dashboard-empty.png', {
      mask: [page.locator('time')],
    });
  });

  test('settings preset apply updates config', async ({ page, request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    await page.goto('/');
    await goToPage(page, 'settings');
    await expect(page.getByRole('heading', { name: /^Settings$/i })).toBeVisible();
    await page.getByRole('button', { name: /Apply preset/i }).click();
    const r = await request.get(`${catcher}/api/v1/config`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.rule_sets?.user_data?.stops?.hot).toBeDefined();
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

  test('config returns all 6 package types with valid stops or cache shape', async ({ request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const r = await request.get(`${catcher}/api/v1/config`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    const ruleSets = body.rule_sets || {};
    const expected = ['user_data', 'app_logs', 'audit_logs', 'business_data', 'job_package', 'cache'];
    for (const ptype of expected) {
      expect(ruleSets[ptype], `missing rule_sets.${ptype}`).toBeDefined();
      const rule = ruleSets[ptype];
      if (rule.cache_seconds != null) {
        expect(typeof rule.cache_seconds).toBe('number');
        expect(rule.cache_seconds).toBeGreaterThanOrEqual(0);
      } else {
        expect(rule.stops, `rule_sets.${ptype} must have stops or cache_seconds`).toBeDefined();
        const stopKeys = ['hot', 'warm', 'cold', 'offsite'];
        for (const k of stopKeys) {
          expect(rule.stops[k], `rule_sets.${ptype}.stops.${k}`).toBeDefined();
          expect(typeof rule.stops[k]).toBe('object');
        }
      }
    }
  });

  test('config/presets endpoint returns scenario presets', async ({ request }) => {
    const catcher = process.env.CATCHER_URL || 'http://127.0.0.1:8000';
    const r = await request.get(`${catcher}/api/v1/config/presets`);
    expect(r.ok()).toBeTruthy();
    const body = await r.json();
    expect(body.presets).toBeDefined();
    expect(body.presets.cloud).toBeDefined();
    expect(body.presets.onprem).toBeDefined();
    expect(body.presets.cost).toBeDefined();
    expect(body.presets.cloud.user_data?.stops?.hot).toBeDefined();
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
  test('packages page with jobs - screenshot (mock data from MANIFEST)', async ({ page, request }) => {
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
    await goToPage(page, 'packages');
    await expect(page.getByText(payloads[0].path).first()).toBeVisible({
      timeout: 10000,
    });
    await expect(page.locator('#packages')).toHaveScreenshot('dashboard-with-jobs.png', {
      mask: [page.locator('time')],
    });
  });
});
