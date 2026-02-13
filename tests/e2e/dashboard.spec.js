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

  test('refresh button has clear affordance', async ({ page }) => {
    await page.goto('/');
    const refresh = page.getByRole('button', { name: /refresh/i });
    await expect(refresh).toBeVisible();
    await expect(refresh).toBeEnabled();
  });

  test('jobs list visible - empty or populated', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /refresh/i }).click();
    const jobsSection = page.getByRole('region', { name: /jobs/i });
    await expect(jobsSection).toBeVisible();
    await expect(jobsSection.locator('.job-list')).toBeVisible();
  });

  test('sources section visible', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: /sources/i })).toBeVisible();
  });

  test('dashboard empty state - screenshot', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /refresh/i }).click();
    await expect(page.getByRole('button', { name: /refresh/i })).toBeEnabled({ timeout: 5000 });
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
    await page.getByRole('button', { name: /refresh/i }).click();
    await expect(page.getByRole('region', { name: /jobs/i }).getByText(payloads[0].path).first()).toBeVisible({
      timeout: 5000,
    });
    await expect(page.locator('main')).toHaveScreenshot('dashboard-with-jobs.png', {
      mask: [page.locator('time')],
    });
  });
});
