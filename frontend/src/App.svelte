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
  const BUCKET_ORDER = ['hot', 'warm', 'cold', 'offsite']

  // Data flow: incoming (left) and outgoing (right) per bucket
  const flowData = $derived.by(() => {
    const transitions = projectionsStore.transitions || []
    const buckets = bucketsStore.buckets || []
    const packages = packagesStore.packages || []
    const isDemo = configStore.demoMode
    const recentThreshold = isDemo ? 30 : 86400 // 30s demo, 1 day prod (seconds)

    const transitionMap = {}
    for (const t of transitions) {
      const key = `${t.bucket_from}→${t.bucket_to}`
      transitionMap[key] = t.count || 0
    }

    const hotBuck = buckets.find((b) => b.name === 'hot')
    const hotCount = hotBuck?.count ?? 0
    const recentIntoHot = packages.filter((p) => {
      if (p.bucket !== 'hot') return false
      const ageSec = p.age_seconds ?? (p.age_days ?? 0) * 86400
      return ageSec < recentThreshold
    }).length

    return {
      incoming: {
        hot: recentIntoHot,
        warm: transitionMap['hot→warm'] ?? 0,
        cold: transitionMap['warm→cold'] ?? 0,
        offsite: transitionMap['cold→offsite'] ?? 0,
      },
      outgoing: {
        hot: transitionMap['hot→warm'] ?? 0,
        warm: transitionMap['warm→cold'] ?? 0,
        cold: transitionMap['cold→offsite'] ?? 0,
        offsite: 0,
      },
      clientsNewPackages: recentIntoHot,
    }
  })

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

  <div class="text-ui-banner" role="complementary">
    <span class="text-ui-label">Terminal alternative:</span>
    <code>python scripts/text-ui.py</code>
    <span class="text-ui-live">or <code>--live</code> for refresh</span>
  </div>

  <!-- Buckets: train-style data flow (Clients → Hot → Warm → Cold → Offsite) -->
  <section id="buckets" aria-labelledby="buckets-heading">
    <h2 id="buckets-heading">Buckets — Data flow from edge to layered storage</h2>
    <p class="flow-desc">Clients send packages into the pipeline; data flows hot → warm → cold → offsite.</p>
    <div class="bucket-train">
      <!-- Clients car: new packages from edge -->
      <div class="train-car train-car-clients">
        <div class="car-connector car-incoming" aria-label="Source">Edge</div>
        <div class="car-body">
          <h3 class="car-title">Clients</h3>
          <div class="car-stats">
            <span class="car-label">Sources</span>
            <span class="car-value">{sourcesStore.sources?.length ?? 0}</span>
          </div>
          <div class="car-clients-list">
            {#each (sourcesStore.sources || []).slice(0, 3) as src}
              <span class="client-chip" title={src.label ?? src.source_id}>{src.source_id}</span>
            {/each}
            {#if (sourcesStore.sources?.length ?? 0) > 3}
              <span class="client-chip">+{(sourcesStore.sources?.length ?? 0) - 3}</span>
            {/if}
          </div>
        </div>
        <div class="car-connector car-outgoing" aria-label="Packages to Hot">
          {#if flowData.clientsNewPackages > 0}
            <span class="flow-badge">+{flowData.clientsNewPackages}</span>
            <span class="flow-arrow">→</span>
          {:else}
            <span class="flow-arrow flow-muted">→</span>
          {/if}
        </div>
      </div>

      <!-- Bucket cars: hot, warm, cold, offsite -->
      {#each BUCKET_ORDER as bucketName}
        {@const bucket = bucketsStore.buckets?.find((b) => b.name === bucketName) ?? { name: bucketName, count: 0, total_bytes: 0 }}
        {@const incoming = flowData.incoming[bucketName] ?? 0}
        {@const outgoing = flowData.outgoing[bucketName] ?? 0}
        <div class="train-car train-car-{bucket.name}">
          <div class="car-connector car-incoming" aria-label="Incoming packages">
            {#if incoming > 0}
              <span class="flow-badge">+{incoming}</span>
            {/if}
            <span class="flow-arrow">←</span>
          </div>
          <div class="car-body">
            <h3 class="car-title">{BUCKET_LABELS[bucket.name] ?? bucket.name}</h3>
            <div class="car-stats">
              <span class="car-label">Files</span>
              <span class="car-value">{bucket.count}</span>
            </div>
            <div class="car-stats">
              <span class="car-label">Storage</span>
              <span class="car-value">{formatBytes(bucket.total_bytes)}</span>
            </div>
          </div>
          <div class="car-connector car-outgoing" aria-label="Packages to next tier">
            {#if outgoing > 0}
              <span class="flow-badge">{outgoing}</span>
              <span class="flow-arrow">→</span>
            {:else}
              <span class="flow-arrow flow-muted">→</span>
            {/if}
          </div>
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

  .flow-desc {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0 0 1rem;
  }

  .bucket-train {
    display: flex;
    align-items: stretch;
    flex-wrap: wrap;
    gap: 0;
  }

  .train-car {
    display: flex;
    align-items: stretch;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    min-height: 110px;
    flex-shrink: 0;
  }

  /* Train coupler: connector between cars */
  .train-car + .train-car .car-incoming {
    margin-left: 2px;
  }

  .train-car-clients {
    border-color: var(--text-muted);
    border-left: 3px solid var(--status-ok);
  }

  .train-car .car-connector {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.25rem;
    padding: 0.4rem 0.5rem;
    min-width: 52px;
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .train-car .car-incoming { border-right: 1px solid var(--border); }
  .train-car .car-outgoing { border-left: 1px solid var(--border); }

  .train-car .car-body {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 0.25rem;
    padding: 0.6rem 1rem;
    min-width: 120px;
    max-width: 160px;
  }

  .train-car .car-title {
    margin: 0;
    font-size: 0.95rem;
    font-weight: 600;
  }

  .train-car .car-stats {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.8rem;
  }

  .train-car .car-label { color: var(--text-muted); }
  .train-car .car-value { font-weight: 600; }

  .train-car .car-clients-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.2rem;
    margin-top: 0.2rem;
  }

  .train-car .client-chip {
    font-size: 0.65rem;
    padding: 0.15rem 0.35rem;
    background: var(--bg-elevated);
    border-radius: 4px;
    max-width: 4.5em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .train-car .flow-badge {
    padding: 0.15rem 0.4rem;
    font-size: 0.7rem;
    font-weight: 600;
    background: var(--status-ok);
    color: var(--bg);
    border-radius: 4px;
  }

  .train-car .flow-arrow {
    font-size: 0.9rem;
  }

  .train-car .flow-arrow.flow-muted {
    opacity: 0.4;
  }

  /* Rectangular train-car styling: distinct accent per bucket, train-like blocks */
  .train-car.bucket-hot {
    border-left: 5px solid var(--bucket-hot);
    box-shadow: inset 0 0 0 1px rgba(63, 185, 80, 0.1);
  }
  .train-car.bucket-warm {
    border-left: 5px solid var(--bucket-warm);
    box-shadow: inset 0 0 0 1px rgba(83, 155, 245, 0.1);
  }
  .train-car.bucket-cold {
    border-left: 5px solid var(--bucket-cold);
    box-shadow: inset 0 0 0 1px rgba(163, 113, 247, 0.1);
  }
  .train-car.bucket-offsite {
    border-left: 5px solid var(--bucket-offsite);
    box-shadow: inset 0 0 0 1px rgba(139, 148, 158, 0.15);
  }

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
  .text-ui-banner { margin: 0.5rem 0; padding: 0.4rem 0.75rem; background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 6px; font-size: 0.8rem; color: var(--text-muted); }
  .text-ui-banner .text-ui-label { margin-right: 0.4rem; }
  .text-ui-banner code { padding: 0.15rem 0.35rem; background: var(--btn-bg); border-radius: 4px; font-size: 0.8em; }
  .text-ui-banner .text-ui-live { margin-left: 0.5rem; color: var(--text-muted); }
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
