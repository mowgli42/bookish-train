/**
 * Phase 1 scenario test: full workflow via API (no UI).
 * Mirrors scripts/phase1-scenario.sh for CI and containerized assessment.
 * Prerequisites: catcher on CATCHER_URL (default http://127.0.0.1:8000).
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

function catcherUrl() {
  return (process.env.CATCHER_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
}

test.describe('Phase 1: Scenario (API workflow)', () => {
  test('full workflow: health → reset → register → ingest → packages → buckets → sources → config → journal → resume → projections', async ({
    request,
  }) => {
    const base = catcherUrl();
    const sourceId = 'phase1-scenario-e2e';

    // 1. Health
    const health = await request.get(`${base}/health`);
    expect(health.ok()).toBeTruthy();
    const healthBody = await health.json();
    expect(healthBody.status).toBe('ok');

    // 2. Demo reset
    const reset = await request.post(`${base}/api/v1/demo/reset`);
    expect(reset.ok()).toBeTruthy();

    // 3. Register source
    const register = await request.post(`${base}/api/v1/sources`, {
      data: { source_id: sourceId, label: 'Phase 1 scenario e2e' },
    });
    expect(register.ok()).toBeTruthy();

    // 4. Ingest from MANIFEST (or one placeholder)
    const payloads =
      mockFiles.length > 0
        ? mockFiles.map((f) => ({
            source_id: sourceId,
            path: f.path,
            checksum: f.checksum,
            size_bytes: f.size_bytes,
            tier_hint: f.tier_hint,
          }))
        : [
            {
              source_id: sourceId,
              path: 'scenario-placeholder.txt',
              checksum: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
              size_bytes: 0,
            },
          ];

    for (const p of payloads) {
      const ingestRes = await request.post(`${base}/api/v1/ingest`, { data: p });
      expect(ingestRes.ok(), `ingest ${p.path}: ${ingestRes.status()}`).toBeTruthy();
    }

    // 5. Packages
    const packagesRes = await request.get(`${base}/api/v1/packages`);
    expect(packagesRes.ok()).toBeTruthy();
    const packages = await packagesRes.json();
    expect(Array.isArray(packages)).toBe(true);
    expect(packages.length).toBeGreaterThanOrEqual(payloads.length);

    // 6. Buckets
    const bucketsRes = await request.get(`${base}/api/v1/buckets`);
    expect(bucketsRes.ok()).toBeTruthy();
    const bucketsBody = await bucketsRes.json();
    expect(bucketsBody.buckets).toBeDefined();
    expect(Array.isArray(bucketsBody.buckets)).toBe(true);

    // 7. Sources
    const sourcesRes = await request.get(`${base}/api/v1/sources`);
    expect(sourcesRes.ok()).toBeTruthy();
    const sources = await sourcesRes.json();
    const found = Array.isArray(sources) ? sources.some((s) => s.source_id === sourceId) : false;
    expect(found).toBeTruthy();

    // 8. Config
    const configRes = await request.get(`${base}/api/v1/config`);
    expect(configRes.ok()).toBeTruthy();
    const config = await configRes.json();
    expect(config.rule_sets != null || config.retention != null).toBeTruthy();

    // 9. Config snapshots / timetable export
    const snapshotsRes = await request.get(`${base}/api/v1/config/snapshots`);
    expect(snapshotsRes.ok()).toBeTruthy();
    const snapshots = await snapshotsRes.json();
    expect(Array.isArray(snapshots)).toBe(true);
    expect(snapshots.length).toBeGreaterThanOrEqual(1);
    expect(snapshots[0].snapshot_id).toBeTruthy();

    const exportRes = await request.get(`${base}/api/v1/config/export`);
    expect(exportRes.ok()).toBeTruthy();
    const exported = await exportRes.json();
    expect(exported.hash).toBeTruthy();
    expect(exported.config.rule_sets).toBeDefined();

    // 10. Journal and resume switch list
    const journalRes = await request.get(`${base}/api/v1/journal?source_id=${sourceId}`);
    expect(journalRes.ok()).toBeTruthy();
    const journal = await journalRes.json();
    expect(Array.isArray(journal)).toBe(true);
    expect(journal.some((e) => e.event_type === 'manifest_created')).toBeTruthy();

    const firstPackage = packages.find((p) => p.source_id === sourceId);
    expect(firstPackage?.job_id).toBeTruthy();
    const failRes = await request.patch(`${base}/api/v1/packages/${firstPackage.job_id}`, {
      data: { status: 'failed', progress_percent: 55, last_error: 'scenario retry check' },
    });
    expect(failRes.ok()).toBeTruthy();

    const resumeRes = await request.get(`${base}/api/v1/sources/${sourceId}/resume`);
    expect(resumeRes.ok()).toBeTruthy();
    const resume = await resumeRes.json();
    expect(resume.count).toBeGreaterThanOrEqual(1);
    expect(resume.switch_list.some((item) => item.package_id === firstPackage.job_id && item.status === 'failed')).toBeTruthy();

    // 11. Projections
    const projRes = await request.get(`${base}/api/v1/projections?days=5`);
    expect(projRes.ok()).toBeTruthy();
    const proj = await projRes.json();
    expect(proj.transitions).toBeDefined();
    expect(Array.isArray(proj.transitions)).toBe(true);
  });
});
