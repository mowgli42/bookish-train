<script>
  import { Grid, WillowDark } from '@svar-ui/svelte-grid'
  import Toaster from './components/Toaster.svelte'
  import BucketCell from './components/BucketCell.svelte'
  import { packagesStore } from './stores/packages.svelte.js'
  import { sourcesStore } from './stores/sources.svelte.js'
  import { bucketsStore } from './stores/buckets.svelte.js'
  import { configStore } from './stores/config.svelte.js'
  import { projectionsStore } from './stores/projections.svelte.js'
  import { statusStore } from './stores/status.svelte.js'

  let mounted = $state(false)
  let projectionDays = $state(5)
  let projectionSeconds = $state(10)

  $effect(() => {
    if (!mounted) return
    packagesStore.fetchPackages()
    sourcesStore.fetchSources()
    bucketsStore.fetchBuckets()
    configStore.fetchConfig()
    statusStore.fetchStatus()
    projectionsStore.fetchProjections(projectionDays, projectionSeconds)
    const id = setInterval(refreshAll, 3000)
    return () => clearInterval(id)
  })

  function refreshAll() {
    packagesStore.fetchPackages()
    sourcesStore.fetchSources()
    bucketsStore.fetchBuckets()
    configStore.fetchConfig()
    statusStore.fetchStatus()
    projectionsStore.fetchProjections(projectionDays, projectionSeconds)
  }

  function formatBytes(n) {
    if (!n) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(n) / Math.log(k))
    return `${parseFloat((n / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }

  const BUCKET_LABELS = { hot: 'Hot', warm: 'Warm', cold: 'Cold', offsite: 'Offsite' }
  function ageLabel(item) {
    if (item?.age_seconds != null) return `${item.age_seconds}s`
    return `${item?.age_days ?? 0}d`
  }

  const packageTypeOptions = [
    { id: 'user_data', label: 'User Data' },
    { id: 'app_logs', label: 'App Logs' },
    { id: 'audit_logs', label: 'Audit Logs' },
    { id: 'business_data', label: 'Business Data' },
    { id: 'job_package', label: 'Job Package' },
    { id: 'cache', label: 'Cache' },
  ]
  const gridColumns = [
    { id: 'path', header: 'Path', flexgrow: 1, width: 200, sort: true, filter: { type: 'text', config: { icon: 'wxi-search', clear: true } } },
    { id: 'source_id', header: 'Source', width: 120, sort: true, filter: { type: 'text', config: { icon: 'wxi-search', clear: true } } },
    { id: 'package_type', header: 'Type', width: 120, sort: true, filter: { type: 'richselect', options: packageTypeOptions }, template: (v) => v ? v.replace(/_/g, ' ') : '—' },
    { id: 'bucket', header: 'Bucket', width: 90, sort: true, filter: { type: 'richselect', options: [{ id: 'hot', label: 'Hot' }, { id: 'warm', label: 'Warm' }, { id: 'cold', label: 'Cold' }, { id: 'offsite', label: 'Offsite' }] }, cell: BucketCell },
    { id: 'status', header: 'Status', width: 100, sort: true, filter: { type: 'richselect', options: [{ id: 'pending', label: 'Pending' }, { id: 'in_progress', label: 'In progress' }, { id: 'completed', label: 'Completed' }, { id: 'failed', label: 'Failed' }] } },
    { id: 'age', header: 'Age', width: 70, sort: true },
    { id: 'progress_percent', header: 'Progress', width: 100, sort: true, template: (v) => v != null ? `${v}%` : '0%' },
    { id: 'size_formatted', header: 'Size', width: 80, sort: true },
    { id: 'checksum', header: 'Checksum', width: 100, template: (v) => v ? (v.length > 12 ? v.slice(0, 12) + '…' : v) : '—' },
  ]

  const gridData = $derived(
    packagesStore.packages.map((p) => ({
      ...p,
      id: p.package_id ?? p.job_id,
      package_type: p.package_type ?? 'user_data',
      age: ageLabel(p),
      size_formatted: formatBytes(p.size_bytes),
    }))
  )

  const clientsGridData = $derived(
    (sourcesStore.sources || []).map((s) => ({
      ...s,
      id: s.source_id,
      dns_name: s.dns_name ?? s.source_id,
      last_upload: s.last_package_uploaded ? new Date(s.last_package_uploaded).toLocaleString() : '—',
    }))
  )
  const clientsGridColumns = [
    { id: 'dns_name', header: 'DNS Name', width: 180, sort: true, filter: 'text' },
    { id: 'ip', header: 'IP', width: 120, sort: true, filter: 'text', template: (v) => v || '—' },
    { id: 'client_type', header: 'Type', width: 90, sort: true, filter: { type: 'richselect', options: [{ id: 'script', label: 'Script' }, { id: 'binary', label: 'Binary' }] }, template: (v) => v || 'script' },
    { id: 'client_version', header: 'Version', width: 100, sort: true, filter: 'text', template: (v) => v || '—' },
    { id: 'in_progress_count', header: 'In Progress', width: 100, sort: true, template: (v) => v ?? 0 },
    { id: 'last_upload', header: 'Last Upload', width: 160, sort: true },
  ]

  const suffix = $derived(configStore.demoMode ? 's' : 'd')

  const hotKey = $derived(configStore.demoMode ? 'hot_seconds' : 'hot_days')
  const warmKey = $derived(configStore.demoMode ? 'warm_seconds' : 'warm_days')
  const coldKey = $derived(configStore.demoMode ? 'cold_seconds' : 'cold_days')
  const offsiteKey = $derived(configStore.demoMode ? 'offsite_seconds' : 'offsite_days')
  const rulesGridData = $derived(
    Object.entries(configStore.ruleSets || {}).map(([ptype, rule]) => ({
      id: ptype,
      type: ptype.replace(/_/g, ' '),
      package_type: ptype,
      hot: rule[hotKey] ?? 0,
      warm: rule[warmKey] ?? 0,
      cold: rule[coldKey] ?? 0,
      offsite: rule[offsiteKey] ?? 0,
      replicate: !!rule.replicate_to_all,
      cache_seconds: rule.cache_seconds ?? (ptype === 'cache' ? null : undefined),
    }))
  )

</script>

<svelte:window onload={() => (mounted = true)} />

<main class="compact">
  <header class="dashboard-header">
    <h1>Edge Backup Dashboard</h1>
    <div class="status-toolbar" role="toolbar" aria-label="Component status">
      <!-- Component status: always visible, color indicates state -->
      <a href="#clients" class="status-tile status-{statusStore.error ? 'error' : (sourcesStore.sources ? 'ok' : 'unknown')}" title="Clients">
        <span class="status-label">Clients</span>
        <span class="status-value">{sourcesStore.sources?.length ?? (statusStore.loading ? '…' : '0')}</span>
      </a>
      <a href="#packages" class="status-tile status-{statusStore.error ? 'error' : (statusStore.status?.components?.catcher?.status ?? 'unknown')}" title="Catcher">
        <span class="status-label">Catcher</span>
        <span class="status-value">{statusStore.status?.components?.catcher?.jobs_count ?? (statusStore.loading ? '…' : '—')}</span>
      </a>
      <a href="#buckets" class="status-tile status-ok" title="Buckets">
        <span class="status-label">Buckets</span>
        <span class="status-value">H:{statusStore.status?.components?.buckets?.hot ?? 0} W:{statusStore.status?.components?.buckets?.warm ?? 0} C:{statusStore.status?.components?.buckets?.cold ?? 0} O:{statusStore.status?.components?.buckets?.offsite ?? 0}</span>
      </a>
      <a href="#rules" class="status-tile status-ok" title="Retention rules">
        <span class="status-label">Rules</span>
        <span class="status-value">View</span>
      </a>
    </div>
  </header>

  {#if configStore.demoMode}
    <div class="demo-banner" role="status">
      Demo mode — retention in seconds. Run <code>python scripts/run-demo.py</code>
    </div>
  {/if}

  <!-- Buckets: spaced with labels -->
  <section id="buckets" aria-labelledby="buckets-heading">
    <h2 id="buckets-heading">Buckets</h2>
    <div class="bucket-cards">
      {#each bucketsStore.buckets as bucket (bucket.name)}
        <div class="bucket-card bucket-{bucket.name}">
          <h3>{BUCKET_LABELS[bucket.name] ?? bucket.name}</h3>
          <div class="bucket-stats">
            <span class="bucket-label">Storage</span>
            <span class="bucket-value">{formatBytes(bucket.total_bytes)}</span>
          </div>
          <div class="bucket-stats">
            <span class="bucket-label">Files</span>
            <span class="bucket-value">{bucket.count}</span>
          </div>
          {#if bucket.incoming_1h != null && bucket.incoming_1h > 0}
            <div class="bucket-stats bucket-incoming">
              <span class="bucket-label">+{bucket.incoming_1h} in {bucket.incoming_window_seconds >= 3600 ? '1h' : '1min'}</span>
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </section>

  <!-- Clients: DataGrid -->
  <section id="clients" aria-labelledby="clients-heading">
    <h2 id="clients-heading">Clients</h2>
    {#if sourcesStore.error}
      <p class="error" role="alert">{sourcesStore.error}</p>
    {:else}
      <div class="grid-wrapper">
        <WillowDark>
          <Grid data={clientsGridData} columns={clientsGridColumns} sizes={{ rowHeight: 36 }} />
        </WillowDark>
      </div>
    {/if}
    {#if !sourcesStore.loading && (!sourcesStore.sources || sourcesStore.sources.length === 0) && !sourcesStore.error}
      <p class="empty">No clients registered.</p>
    {/if}
  </section>

  <!-- Packages: SVAR DataGrid -->
  <section id="packages" aria-labelledby="packages-heading">
    <h2 id="packages-heading">Packages</h2>
    {#if packagesStore.error}
      <p class="error" role="alert">{packagesStore.error}</p>
    {:else}
      <div class="grid-wrapper">
        <WillowDark>
          <Grid
            data={gridData}
            columns={gridColumns}
            sizes={{ rowHeight: 36 }}
          />
        </WillowDark>
      </div>
    {/if}
    {#if !packagesStore.loading && packagesStore.packages.length === 0 && !packagesStore.error}
      <p class="empty">No packages yet.</p>
    {/if}
  </section>

  <!-- Retention rulesets: DataGrid of rule types per bucket -->
  <section id="rules" aria-labelledby="rules-heading">
    <h2 id="rules-heading">Retention Rules</h2>
    <p class="rule-desc">Per-package-type retention: how long each type stays in each bucket. Business data replicates to all tiers.</p>
    {#if rulesGridData.length > 0}
      <div class="rules-grid-wrapper">
        <WillowDark>
          <Grid
            data={rulesGridData}
            columns={[
              { id: 'type', header: 'Type', width: 130 },
              { id: 'hot', header: `Hot (${suffix})`, width: 85 },
              { id: 'warm', header: `Warm (${suffix})`, width: 95 },
              { id: 'cold', header: `Cold (${suffix})`, width: 95 },
              { id: 'offsite', header: `Offsite (${suffix})`, width: 105 },
              { id: 'replicate', header: 'Replicate', width: 90, template: (v) => v ? 'Yes' : 'No' },
              { id: 'cache_ttl', header: 'Cache TTL (s)', width: 110, template: (v, row) => row.cache_seconds != null ? String(row.cache_seconds) : '—' },
            ]}
            sizes={{ rowHeight: 36 }}
          />
        </WillowDark>
      </div>
    {:else if configStore.loading}
      <p class="empty">Loading rules…</p>
    {:else}
      <p class="empty">No rule sets configured.</p>
    {/if}
  </section>

  <!-- Projections -->
  <section id="projections" aria-labelledby="projections-heading">
    <h2 id="projections-heading">Projections</h2>
    {#if configStore.demoMode}
      <input type="number" bind:value={projectionSeconds} min="1" max="120" />s
    {:else}
      <input type="number" bind:value={projectionDays} min="1" max="365" />d
    {/if}
    <button type="button" onclick={() => projectionsStore.fetchProjections(projectionDays, projectionSeconds)}>Update</button>
    {#if projectionsStore.transitions.length > 0}
      <ul class="transitions-list">
        {#each projectionsStore.transitions as t}
          <li><strong>{t.bucket_from} → {t.bucket_to}</strong>: {t.count}</li>
        {/each}
      </ul>
    {:else}
      <p class="empty">No transitions projected.</p>
    {/if}
  </section>


  <Toaster />

  <!-- Deleted: messaging -->
  <p class="deleted-messaging">
    Updated data is always coming in — retention policy deletes oldest, keeps latest.
  </p>
</main>

<style>
  :global(body) {
    --bg: #0d1117;
    --bg-elevated: #161b22;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --border: #30363d;
    --link: #58a6ff;
    --link-hover: #79b8ff;
    --btn-bg: #21262d;
    --btn-border: #30363d;
    --bucket-hot: #3fb950;
    --bucket-warm: #539bf5;
    --bucket-cold: #a371f7;
    --bucket-offsite: #8b949e;
    --badge-pending: #9e6a03;
    --badge-pending-bg: #3d2e00;
    --badge-in_progress: #539bf5;
    --badge-in_progress-bg: #1c3d6a;
    --badge-completed: #3fb950;
    --badge-completed-bg: #1a4d2e;
    --badge-failed: #f85149;
    --error: #f85149;
    --status-ok: #3fb950;
    --status-idle: #d29922;
    --status-error: #f85149;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    min-height: 100vh;
  }

  main.compact {
    width: 100%;
    min-height: 100vh;
    padding: 1rem 1.25rem;
    box-sizing: border-box;
  }

  .dashboard-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-bottom: 1rem;
  }

  .dashboard-header h1 {
    margin: 0;
  }

  .status-toolbar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
    padding: 0.5rem 0.75rem;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  .status-tile {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    padding: 0.35rem 0.6rem;
    border-radius: 6px;
    text-decoration: none;
    font-size: 0.8rem;
    min-width: 4rem;
    border-left: 4px solid;
  }
  .status-tile .status-label { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); }
  .status-tile .status-value { font-weight: 600; color: inherit; }
  .status-tile.status-active { border-left-color: var(--status-ok); color: var(--status-ok); }
  .status-tile.status-idle { border-left-color: var(--status-idle); color: var(--status-idle); }
  .status-tile.status-ok { border-left-color: var(--status-ok); color: var(--status-ok); }
  .status-tile.status-error { border-left-color: var(--error); color: var(--error); }
  .status-tile.status-unknown { border-left-color: var(--text-muted); color: var(--text-muted); }
  .status-tile:hover { background: rgba(255,255,255,0.04); }


  section {
    margin-bottom: 1rem;
    padding: 0.75rem 1rem;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
  }

  h1 { font-size: 1.25rem; }
  h2 { font-size: 1rem; margin: 0 0 0.5rem; }

  .bucket-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 1rem;
  }

  .bucket-card {
    padding: 0.75rem 1rem;
    border-radius: 8px;
    border-left: 4px solid;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .bucket-card h3 { margin: 0 0 0.35rem; font-size: 0.95rem; }
  .bucket-stats { display: flex; justify-content: space-between; align-items: baseline; font-size: 0.875rem; }
  .bucket-stats .bucket-label { color: var(--text-muted); font-size: 0.8rem; }
  .bucket-stats .bucket-value { font-weight: 600; }
  .bucket-stats.bucket-incoming .bucket-label { color: var(--status-ok); font-size: 0.75rem; }
  .bucket-card.bucket-hot { border-left-color: var(--bucket-hot); }
  .bucket-card.bucket-warm { border-left-color: var(--bucket-warm); }
  .bucket-card.bucket-cold { border-left-color: var(--bucket-cold); }
  .bucket-card.bucket-offsite { border-left-color: var(--bucket-offsite); }

  .grid-wrapper {
    min-height: 320px;
    border: 1px solid var(--border);
    border-radius: 6px;
    overflow: hidden;
  }

  .grid-wrapper :global(.wx-grid) {
    font-size: 0.875rem;
  }

  .badge {
    padding: 0.15rem 0.4rem;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    border-radius: 4px;
  }

  .badge-pending { background: var(--badge-pending-bg); color: var(--badge-pending); }
  .badge-in_progress { background: var(--badge-in_progress-bg); color: var(--badge-in_progress); }
  .badge-completed { background: var(--badge-completed-bg); color: var(--badge-completed); }
  .badge-failed { background: #5d1f1a; color: var(--badge-failed); }
  .bucket-badge.bucket-hot { background: #1a4d2e; color: var(--bucket-hot); }
  .bucket-badge.bucket-warm { background: #1c3d6a; color: var(--bucket-warm); }
  .bucket-badge.bucket-cold { background: #2d1f5d; color: var(--bucket-cold); }
  .bucket-badge.bucket-offsite { background: #21262d; color: var(--bucket-offsite); }

  .retention-input { width: 4ch; margin: 0 0.15rem; padding: 0.2rem; }
  .rule-desc { font-size: 0.875rem; color: var(--text-muted); margin: 0 0 0.5rem; }
  .rules-grid-wrapper { min-height: 200px; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }

  .transitions-list { list-style: none; padding: 0; font-size: 0.875rem; }
  .transitions-list li { padding: 0.25rem 0; }

  .deleted-messaging {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 1rem 0;
    padding: 0.5rem;
    background: var(--bg-elevated);
    border-radius: 4px;
  }

  .meta { font-size: 0.75rem; color: var(--text-muted); }
  .empty { color: var(--text-muted); font-size: 0.875rem; }
  .demo-banner { margin: 0.5rem 0; padding: 0.5rem; background: #1c3d6a; border-radius: 6px; font-size: 0.85rem; }
  .error-banner { margin: 0.5rem 0; padding: 0.5rem 0.75rem; background: rgba(248,81,73,0.15); border: 1px solid var(--error); border-radius: 6px; color: var(--error); font-size: 0.875rem; }
  button {
    padding: 0.35rem 0.75rem;
    cursor: pointer;
    border: 1px solid var(--btn-border);
    border-radius: 6px;
    background: var(--btn-bg);
    color: var(--text);
    font-size: 0.875rem;
  }
  button:hover { background: var(--border); }
  button:focus-visible { outline: 2px solid var(--link); outline-offset: 2px; }
  input {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
    padding: 0.25rem 0.4rem;
  }
  input:focus { outline: 2px solid var(--link); outline-offset: 0; }
</style>
