<script>
  import { Grid, WillowDark } from '@svar-ui/svelte-grid'
  import Toaster from './components/Toaster.svelte'
  import BucketCell from './components/BucketCell.svelte'
  import RuleEditForm from './components/RuleEditForm.svelte'
  import { toasterStore } from './stores/toaster.svelte.js'
  import { packagesStore } from './stores/packages.svelte.js'
  import { sourcesStore } from './stores/sources.svelte.js'
  import { bucketsStore } from './stores/buckets.svelte.js'
  import { configStore } from './stores/config.svelte.js'
  import { projectionsStore } from './stores/projections.svelte.js'
  import { statusStore } from './stores/status.svelte.js'

  let mounted = $state(false)
  let projectionDays = $state(5)
  let projectionSeconds = $state(10)
  /** Page refresh interval in seconds (1–300). Used for polling packages, status, etc. */
  let refreshIntervalSeconds = $state(5)
  let seedLoading = $state(false)
  let seedMessage = $state(null)

  function refreshAll() {
    packagesStore.fetchPackages()
    sourcesStore.fetchSources()
    bucketsStore.fetchBuckets()
    configStore.fetchConfig()
    statusStore.fetchStatus()
    projectionsStore.fetchProjections(projectionDays, projectionSeconds)
  }

  $effect(() => {
    if (!mounted) return
    refreshAll()
    const ms = Math.max(1000, Math.min(300000, refreshIntervalSeconds * 1000))
    const id = setInterval(refreshAll, ms)
    return () => clearInterval(id)
  })

  async function seedDemoData() {
    seedLoading = true
    seedMessage = null
    try {
      const r = await fetch('/api/v1/demo/seed?source_id=demo-seed', { method: 'POST' })
      const data = await r.json()
      seedMessage = r.ok ? `Seeded ${data.seeded ?? 0} packages` : (data.detail ?? 'Seed failed')
      if (r.ok) refreshAll()
    } catch (e) {
      seedMessage = e.message || 'Seed failed'
    } finally {
      seedLoading = false
    }
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
    const packages = packagesStore.packages || []
    const isDemo = configStore.demoMode
    const recentThreshold = isDemo ? 30 : 86400 // 30s demo, 1 day prod (seconds)

    const transitionMap = {}
    for (const t of transitions) {
      const key = `${t.bucket_from}→${t.bucket_to}`
      transitionMap[key] = t.count || 0
    }

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
  const waitKey = $derived(configStore.demoMode ? 'wait_seconds' : 'wait_days')

  /** Extract wait value from stop object (stops format). Returns number or null for never_delete. */
  function stopWait(stop) {
    if (!stop?.enabled) return 0
    if (stop?.never_delete) return null // ∞
    const w = stop?.[waitKey]
    return w != null ? w : 0
  }

  /** Single-pass aggregation: packages by (package_type, bucket) for live counts. */
  const packagesByTypeAndBucket = $derived.by(() => {
    const packages = packagesStore.packages || []
    const acc = {}
    for (const p of packages) {
      const ptype = p.package_type || 'user_data'
      const bucket = p.bucket || 'hot'
      if (!acc[ptype]) acc[ptype] = { hot: 0, warm: 0, cold: 0, offsite: 0 }
      if (BUCKET_ORDER.includes(bucket)) acc[ptype][bucket] = (acc[ptype][bucket] ?? 0) + 1
    }
    return acc
  })

  /** Shared lines data: rules + per-type-per-bucket counts. Used by Rules grid and Train Lines grid. */
  const linesData = $derived.by(() => {
    const ruleSets = configStore.ruleSets || {}
    const counts = packagesByTypeAndBucket
    return Object.entries(ruleSets).map(([ptype, rule]) => {
      const lineCounts = counts[ptype] || { hot: 0, warm: 0, cold: 0, offsite: 0 }
      const stops = rule?.stops || {}
      const hot = ptype === 'cache' ? 0 : stopWait(stops.hot)
      const warm = ptype === 'cache' ? 0 : stopWait(stops.warm)
      const cold = ptype === 'cache' ? 0 : stopWait(stops.cold)
      const offsite = ptype === 'cache' ? 0 : stopWait(stops.offsite)
      return {
        id: ptype,
        type: ptype.replace(/_/g, ' '),
        package_type: ptype,
        hot,
        warm,
        cold,
        offsite,
        replicate: !!rule?.replicate_to_all,
        cache_seconds: rule?.cache_seconds ?? (ptype === 'cache' ? null : undefined),
        counts: lineCounts,
      }
    })
  })

  const rulesGridData = $derived(
    linesData.map(({ id, type, package_type, hot, warm, cold, offsite, replicate, cache_seconds }) => ({
      id,
      type,
      package_type,
      hot,
      warm,
      cold,
      offsite,
      replicate,
      cache_seconds,
    }))
  )

  let currentPage = $state('tracks')
  /** Selected stop on tracks map for detail panel (null = none). */
  let selectedBucket = $state(null)
  /** Package type being edited (null = modal closed). */
  let editingRulePtype = $state(null)
  /** Package type selected in dropdown for Edit button. */
  let editRuleSelect = $state('user_data')

  function go(page) {
    currentPage = page
    if (typeof window !== 'undefined') {
      window.location.hash = page
    }
  }
  $effect(() => {
    if (typeof window === 'undefined') return
    const onHash = () => {
      const h = (window.location.hash || '#').slice(1) || 'tracks'
      if (['tracks', 'clients', 'packages', 'rules', 'settings', 'stops'].includes(h)) currentPage = h
    }
    onHash()
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  })

  const clientsStatus = $derived(
    statusStore.error ? 'error'
    : sourcesStore.loading ? 'uninitialized'
    : (sourcesStore.sources?.length ?? 0) === 0 ? 'uninitialized'
    : 'ok'
  )
  const catcherStatus = $derived(
    statusStore.error ? 'error'
    : statusStore.status?.components?.catcher?.status ?? 'uninitialized'
  )
  const bucketsStatus = $derived(statusStore.error ? 'error' : (statusStore.status?.components?.buckets ? 'ok' : 'uninitialized'))

  /** Per-stop status and detail for Stops page and stop detail panel. */
  const stopsData = $derived.by(() => {
    const buckets = bucketsStore.buckets || []
    const statusBuckets = statusStore.status?.components?.buckets || {}
    return BUCKET_ORDER.map((name) => {
      const bucket = buckets.find((b) => b.name === name)
      const count = bucket?.count ?? statusBuckets[name] ?? 0
      return {
        name,
        label: BUCKET_LABELS[name] ?? name,
        status: count > 0 ? 'ok' : 'empty',
        count,
        total_bytes: bucket?.total_bytes ?? 0,
        sample: bucket?.sample ?? [],
      }
    })
  })

  const selectedBucketDetail = $derived(selectedBucket ? stopsData.find((s) => s.name === selectedBucket) : null)
</script>

<svelte:window onload={() => (mounted = true)} />

<main class="compact">
  <header class="dashboard-header">
    <h1 class="brand">Edge Backup Railway</h1>
    <nav class="main-nav" aria-label="Main">
      <a class="nav-link" class:active={currentPage === 'tracks'} href="#tracks" onclick={(e) => { e.preventDefault(); go('tracks') }}>Tracks</a>
      <a class="nav-link" class:active={currentPage === 'stops'} href="#stops" onclick={(e) => { e.preventDefault(); go('stops') }}>Stops</a>
      <a class="nav-link" class:active={currentPage === 'clients'} href="#clients" onclick={(e) => { e.preventDefault(); go('clients') }}>Clients</a>
      <a class="nav-link" class:active={currentPage === 'packages'} href="#packages" onclick={(e) => { e.preventDefault(); go('packages') }}>Packages</a>
      <a class="nav-link" class:active={currentPage === 'rules'} href="#rules" onclick={(e) => { e.preventDefault(); go('rules') }}>Rules</a>
      <a class="nav-link nav-link-icon" class:active={currentPage === 'settings'} href="#settings" onclick={(e) => { e.preventDefault(); go('settings') }} title="Settings" aria-label="Settings">
        <svg class="gear-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        <span class="nav-link-text">Settings</span>
      </a>
    </nav>
    <div class="stoplights" role="status" aria-label="Backend status">
      <button type="button" class="stoplight-btn status-{clientsStatus}" title="Clients: {sourcesStore.sources?.length ?? 0} sources" onclick={() => go('clients')}>Clients</button>
      <button type="button" class="stoplight-btn status-{catcherStatus}" title="Catcher: {statusStore.status?.components?.catcher?.jobs_count ?? 0} jobs" onclick={() => go('packages')}>Catcher</button>
      <button type="button" class="stoplight-btn status-{bucketsStatus}" title="Buckets: H:{statusStore.status?.components?.buckets?.hot ?? 0} W:{statusStore.status?.components?.buckets?.warm ?? 0} C:{statusStore.status?.components?.buckets?.cold ?? 0} O:{statusStore.status?.components?.buckets?.offsite ?? 0}" onclick={() => go(bucketsStatus === 'error' ? 'tracks' : 'stops')}>Buckets</button>
    </div>
  </header>

  {#if configStore.demoMode}
    <div class="demo-warning-banner" role="alert">
      <span class="demo-warning-label">Demo mode</span>
      Retention in seconds. Run <code>python scripts/run-demo.py</code>
    </div>
  {/if}

  {#if currentPage === 'tracks'}
    <section class="train-map-section" id="buckets" aria-labelledby="buckets-heading">
      <h2 id="buckets-heading" class="train-heading">Track diagram</h2>
      <div class="track-diagram" aria-label="Data flow: Clients to Hot to Warm to Cold to Offsite">
        <svg class="track-svg" viewBox="0 0 800 120" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          <defs>
            <linearGradient id="rail-gradient" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stop-color="var(--text-muted)" stop-opacity="0.5" />
              <stop offset="100%" stop-color="var(--text-muted)" stop-opacity="0.9" />
            </linearGradient>
          </defs>
          <!-- Rails (two parallel lines) -->
          <path d="M 40 50 L 760 50" fill="none" stroke="url(#rail-gradient)" stroke-width="3" stroke-linecap="round" />
          <path d="M 40 58 L 760 58" fill="none" stroke="url(#rail-gradient)" stroke-width="2" stroke-linecap="round" />
          <!-- Station nodes: clickable; bucket stops open stop detail -->
          <g class="track-station track-station-clickable" data-name="clients" role="button" tabindex="0" title="View clients" onclick={() => go('clients')} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go('clients') } }}><circle cx="80" cy="54" r="14" class="station-node station-clients" /><text x="80" y="88" class="station-label" text-anchor="middle">Clients</text><text x="80" y="105" class="station-count" text-anchor="middle">{sourcesStore.sources?.length ?? 0}</text></g>
          <g class="track-station track-station-clickable" data-name="hot" role="button" tabindex="0" title="Hot – view details" onclick={() => selectedBucket = 'hot'} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectedBucket = 'hot' } }}><circle cx="220" cy="54" r="14" class="station-node station-hot" /><text x="220" y="88" class="station-label" text-anchor="middle">Hot</text><text x="220" y="105" class="station-count" text-anchor="middle">{bucketsStore.buckets?.find(b => b.name === 'hot')?.count ?? 0}</text></g>
          <g class="track-station track-station-clickable" data-name="warm" role="button" tabindex="0" title="Warm – view details" onclick={() => selectedBucket = 'warm'} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectedBucket = 'warm' } }}><circle cx="360" cy="54" r="14" class="station-node station-warm" /><text x="360" y="88" class="station-label" text-anchor="middle">Warm</text><text x="360" y="105" class="station-count" text-anchor="middle">{bucketsStore.buckets?.find(b => b.name === 'warm')?.count ?? 0}</text></g>
          <g class="track-station track-station-clickable" data-name="cold" role="button" tabindex="0" title="Cold – view details" onclick={() => selectedBucket = 'cold'} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectedBucket = 'cold' } }}><circle cx="500" cy="54" r="14" class="station-node station-cold" /><text x="500" y="88" class="station-label" text-anchor="middle">Cold</text><text x="500" y="105" class="station-count" text-anchor="middle">{bucketsStore.buckets?.find(b => b.name === 'cold')?.count ?? 0}</text></g>
          <g class="track-station track-station-clickable" data-name="offsite" role="button" tabindex="0" title="Offsite – view details" onclick={() => selectedBucket = 'offsite'} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectedBucket = 'offsite' } }}><circle cx="720" cy="54" r="14" class="station-node station-offsite" /><text x="720" y="88" class="station-label" text-anchor="middle">Offsite</text><text x="720" y="105" class="station-count" text-anchor="middle">{bucketsStore.buckets?.find(b => b.name === 'offsite')?.count ?? 0}</text></g>
          <!-- Segment flow (outgoing to next station) -->
          <text x="150" y="42" class="segment-flow" text-anchor="middle">{flowData.clientsNewPackages}</text>
          <text x="290" y="42" class="segment-flow" text-anchor="middle">{flowData.outgoing?.hot ?? 0}</text>
          <text x="430" y="42" class="segment-flow" text-anchor="middle">{flowData.outgoing?.warm ?? 0}</text>
          <text x="610" y="42" class="segment-flow" text-anchor="middle">{flowData.outgoing?.cold ?? 0}</text>
        </svg>
      </div>
      {#if selectedBucketDetail}
        <div class="train-car-detail" role="region" aria-labelledby="train-car-heading">
          <div class="train-car-header">
            <h3 id="train-car-heading" class="train-car-title">{selectedBucketDetail.label} – stop</h3>
            <button type="button" class="train-car-close" onclick={() => selectedBucket = null} title="Close">×</button>
          </div>
          <dl class="train-car-stats">
            <dt>Status</dt>
            <dd><span class="stop-status stop-status-{selectedBucketDetail.status}">{selectedBucketDetail.status === 'ok' ? 'Active' : 'Empty'}</span></dd>
            <dt>Packages</dt>
            <dd>{selectedBucketDetail.count}</dd>
            <dt>Total size</dt>
            <dd>{formatBytes(selectedBucketDetail.total_bytes)}</dd>
          </dl>
          {#if selectedBucketDetail.sample.length > 0}
            <p class="train-car-sample-label">Sample</p>
            <ul class="train-car-sample">
              {#each selectedBucketDetail.sample as item}
                <li><span class="train-car-path" title={item.path}>{item.path}</span> <span class="train-car-meta">{item.source_id} · {item.age_days != null ? item.age_days + 'd' : (item.age_seconds ?? 0) + 's'}</span></li>
              {/each}
            </ul>
          {/if}
          <a href="#stops" class="train-car-link" onclick={(e) => { e.preventDefault(); selectedBucket = null; go('stops') }}>View all stops</a>
        </div>
      {/if}
    </section>

    <section class="train-lines-section" id="migration-rules" aria-labelledby="train-lines-heading">
        <h2 id="train-lines-heading" class="train-heading">Migration rules by type</h2>
        {#if linesData.length > 0}
          <div class="train-lines-grid" role="grid" aria-label="Retention rules per package type">
            <div class="train-lines-header" role="row">
              <div class="train-lines-cell train-lines-label" role="columnheader">Type</div>
              {#each BUCKET_ORDER as b}
                <div class="train-lines-cell" role="columnheader">{BUCKET_LABELS[b] ?? b}</div>
              {/each}
              <div class="train-lines-cell train-lines-notes" role="columnheader"></div>
            </div>
            {#each linesData as line}
              {#if line.cache_seconds != null}
                <div class="train-lines-row train-lines-row-cache" role="row">
                  <div class="train-lines-cell train-lines-label" role="gridcell">{line.type}</div>
                  <div class="train-lines-cell train-lines-cache-badge" role="gridcell">Delete after {line.cache_seconds}s</div>
                </div>
              {:else}
                <div class="train-lines-row" role="row">
                  <div class="train-lines-cell train-lines-label" role="gridcell">{line.type}</div>
                  {#each BUCKET_ORDER as b}
                    <div class="train-lines-cell" role="gridcell">{#if line[b] == null}∞{:else}{line[b]} {suffix}{/if} ({line.counts[b] ?? 0})</div>
                  {/each}
                  <div class="train-lines-cell train-lines-notes" role="gridcell">{#if line.replicate}[replicate]{/if}</div>
                </div>
              {/if}
            {/each}
          </div>
          <a href="#rules" class="train-lines-link" onclick={(e) => { e.preventDefault(); go('rules') }}>Edit rules</a>
        {:else if configStore.loading}
          <p class="empty">Loading rules…</p>
        {:else}
          <p class="empty">No rules configured.</p>
        {/if}
    </section>
  {/if}

  {#if currentPage === 'stops'}
  <section id="stops" class="depot-page" aria-labelledby="stops-heading">
    <h2 id="stops-heading" class="train-heading">Stops (buckets)</h2>
    <p class="depot-desc">Status and detail for each bucket. Click a station on the Train map to see its detail there.</p>
    {#if bucketsStore.error}
      <p class="error" role="alert">{bucketsStore.error}</p>
    {:else}
      <div class="stops-grid">
        {#each stopsData as stop}
          <article class="stop-card stop-card-{stop.name}" aria-labelledby="stop-title-{stop.name}">
            <h3 id="stop-title-{stop.name}" class="stop-card-title">{stop.label}</h3>
            <div class="stop-card-status">
              <span class="stop-status stop-status-{stop.status}" aria-label="Status: {stop.status === 'ok' ? 'Active' : 'Empty'}">{stop.status === 'ok' ? 'Active' : 'Empty'}</span>
            </div>
            <dl class="stop-card-stats">
              <dt>Packages</dt>
              <dd>{stop.count}</dd>
              <dt>Total size</dt>
              <dd>{formatBytes(stop.total_bytes)}</dd>
            </dl>
            {#if stop.sample.length > 0}
              <p class="stop-sample-label">Sample</p>
              <ul class="stop-sample-list">
                {#each stop.sample as item}
                  <li><span class="stop-path" title={item.path}>{item.path}</span> <span class="stop-meta">{item.source_id} · {item.age_days != null ? item.age_days + 'd' : (item.age_seconds ?? 0) + 's'}</span></li>
                {/each}
              </ul>
            {:else if stop.count === 0}
              <p class="empty">No packages in this bucket.</p>
            {/if}
          </article>
        {/each}
      </div>
    {/if}
  </section>
  {/if}

  {#if currentPage === 'clients'}
  <section id="clients" class="depot-page" aria-labelledby="clients-heading">
    <h2 id="clients-heading" class="train-heading">Clients</h2>
    <div class="clients-summary" role="status">
      <div class="clients-summary-item"><span class="clients-summary-label">Sources</span> <strong>{sourcesStore.sources?.length ?? 0}</strong></div>
      <div class="clients-summary-item"><span class="clients-summary-label">In progress</span> <strong>{(sourcesStore.sources || []).reduce((n, s) => n + (s.in_progress_count ?? 0), 0)}</strong></div>
    </div>
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
  {/if}

  {#if currentPage === 'packages'}
  <section id="packages" class="depot-page" aria-labelledby="packages-heading">
    <h2 id="packages-heading" class="train-heading">Package tracking</h2>
    <p class="depot-desc">Client ingestion through cold storage. Package details by tier.</p>
    <!-- Pipeline by tier with package info -->
    <div class="pipeline-by-tier">
      {#each BUCKET_ORDER as bucketName}
        {@const tierPackages = packagesStore.packages.filter((p) => p.bucket === bucketName)}
        <div class="pipeline-tier">
          <h3 class="pipeline-tier-name">{BUCKET_LABELS[bucketName] ?? bucketName}</h3>
          <div class="pipeline-tier-list">
            {#if tierPackages.length === 0}
              <p class="empty">—</p>
            {:else}
              {#each tierPackages as p}
                <div class="pipeline-pkg">
                  <span class="pkg-path" title={p.path}>{p.path}</span>
                  <span class="pkg-meta">{p.source_id ?? '—'} · {ageLabel(p)} · {formatBytes(p.size_bytes)}</span>
                </div>
              {/each}
            {/if}
          </div>
        </div>
      {/each}
    </div>
    <h3 class="depot-subhead">All packages</h3>
    {#if packagesStore.error}
      <p class="error" role="alert">{packagesStore.error}</p>
    {:else}
      <div class="grid-wrapper depot-grid">
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
  {/if}

  {#if currentPage === 'rules'}
  <section id="rules" class="depot-page" aria-labelledby="rules-heading">
    <h2 id="rules-heading" class="train-heading">Retention Rules</h2>
    <p class="rule-desc">Per-package-type retention: how long each type stays in each bucket. Business data replicates to all tiers.</p>
    <div class="rules-legend" role="group" aria-label="Column and value meanings">
      <p class="rules-legend-item"><strong>Stops:</strong> Hot → Warm → Cold → Offsite. Each column shows wait time ({configStore.demoMode ? 'seconds' : 'days'}) in that bucket. <code>skip</code> = tier disabled; <code>∞</code> = never delete (offsite only).</p>
      <p class="rules-legend-item"><strong>Cache:</strong> Kept in hot storage for the specified time (seconds), then deleted.</p>
      <p class="rules-legend-item"><strong>Replicate:</strong> Yes = copy to all tiers (e.g. business data).</p>
    </div>
    {#if rulesGridData.length > 0}
      <div class="rules-grid-wrapper">
        <WillowDark>
          <Grid
            data={rulesGridData}
            columns={[
              { id: 'type', header: 'Type', width: 130 },
              { id: 'hot', header: `Hot (${suffix})`, width: 85, template: (v) => v == null ? '—' : (v === 0 ? 'skip' : String(v)) },
              { id: 'warm', header: `Warm (${suffix})`, width: 95, template: (v) => v == null ? '—' : (v === 0 ? 'skip' : String(v)) },
              { id: 'cold', header: `Cold (${suffix})`, width: 95, template: (v) => v == null ? '—' : (v === 0 ? 'skip' : String(v)) },
              { id: 'offsite', header: `Offsite (${suffix})`, width: 105, template: (v) => v == null ? '∞' : (v === 0 ? 'skip' : String(v)) },
              { id: 'replicate', header: 'Replicate', width: 90, template: (v) => v ? 'Yes' : 'No' },
              { id: 'cache_ttl', header: 'Cache TTL (s)', width: 110, template: (v, row) => row.cache_seconds != null ? String(row.cache_seconds) : '—' },
            ]}
            sizes={{ rowHeight: 36 }}
          />
        </WillowDark>
      </div>
      <div class="rules-edit-bar">
        <label class="rules-edit-label">
          <span>Edit rule:</span>
          <select class="rules-edit-select" bind:value={editRuleSelect}>
            {#each Object.keys(configStore.ruleSets || {}) as ptype}
              <option value={ptype}>{ptype.replace(/_/g, ' ')}</option>
            {/each}
          </select>
        </label>
        <button type="button" class="rules-edit-btn" onclick={() => (editingRulePtype = editRuleSelect)}>Edit</button>
      </div>
    {:else if configStore.loading}
      <p class="empty">Loading rules…</p>
    {:else}
      <p class="empty">No rule sets configured.</p>
    {/if}

    {#if editingRulePtype}
      <div
        class="modal-backdrop"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-rule-title"
        tabindex="-1"
        onclick={(e) => e.target === e.currentTarget && (editingRulePtype = null)}
        onkeydown={(e) => e.key === 'Escape' && (editingRulePtype = null)}
      >
        <div class="modal-content">
          <h3 id="edit-rule-title" class="modal-title">Edit rule: {editingRulePtype?.replace(/_/g, ' ')}</h3>
          <RuleEditForm
            rule={configStore.ruleSets?.[editingRulePtype]}
            packageType={editingRulePtype}
            isDemo={configStore.demoMode}
            onSave={async (payload) => {
              await configStore.patchConfig(payload)
              toasterStore.success('Rules updated')
            }}
            onCancel={() => (editingRulePtype = null)}
          />
        </div>
      </div>
    {/if}
  </section>
  {/if}

  {#if currentPage === 'settings'}
  <section id="settings" class="depot-page settings-page" aria-labelledby="settings-heading">
    <h2 id="settings-heading" class="train-heading settings-heading">
      <svg class="gear-icon heading-icon" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
      Settings
    </h2>

    <div class="settings-grid">
      <div class="setting-group" role="group" aria-labelledby="refresh-label">
        <h3 id="refresh-label" class="setting-group-title">Data refresh</h3>
        <label class="setting-row">
          <span class="setting-label">Page refresh interval</span>
          <input type="number" class="setting-input" bind:value={refreshIntervalSeconds} min="1" max="300" step="1" />
          <span class="setting-suffix">seconds</span>
        </label>
        <p class="setting-hint">How often the dashboard fetches packages, status, and projections (1–300 s).</p>
      </div>

      <div class="setting-group" role="group" aria-labelledby="projections-label">
        <h3 id="projections-label" class="setting-group-title">Projections</h3>
        <div class="setting-row">
          {#if configStore.demoMode}
            <label class="setting-inline"><span class="setting-label">Horizon</span>
              <input type="number" class="setting-input setting-input-narrow" bind:value={projectionSeconds} min="1" max="120" />s
            </label>
          {:else}
            <label class="setting-inline"><span class="setting-label">Horizon</span>
              <input type="number" class="setting-input setting-input-narrow" bind:value={projectionDays} min="1" max="365" />d
            </label>
          {/if}
          <button type="button" class="setting-btn" onclick={() => projectionsStore.fetchProjections(projectionDays, projectionSeconds)}>Update</button>
        </div>
        {#if projectionsStore.transitions.length > 0}
          <ul class="transitions-list" aria-label="Upcoming bucket transitions">
            {#each projectionsStore.transitions as t}
              <li><strong>{t.bucket_from} → {t.bucket_to}</strong>: {t.count}</li>
            {/each}
          </ul>
        {:else}
          <p class="empty">No transitions projected. Click Update to fetch.</p>
        {/if}
      </div>

      <div class="setting-group" role="group" aria-labelledby="demo-label">
        <h3 id="demo-label" class="setting-group-title">Demo</h3>
        {#if configStore.demoMode}
          <p class="setting-hint">Demo mode is active. Retention uses seconds.</p>
          <div class="setting-row">
            <button type="button" class="setting-btn" disabled={seedLoading} onclick={seedDemoData}>Seed data</button>
            {#if seedMessage}
              <span class="setting-feedback">{seedMessage}</span>
            {/if}
          </div>
        {:else}
          <p class="setting-hint">Start backend with <code>DEMO_MODE=1</code> to enable demo options.</p>
        {/if}
      </div>
    </div>
  </section>
  {/if}

  <Toaster />

  {#if currentPage === 'tracks'}
  <p class="deleted-messaging">
    Updated data is always coming in — retention policy deletes oldest, keeps latest.
    Terminal: <code>python scripts/text-ui.py</code> or <code>--live</code>.
  </p>
  {/if}
</main>

<style>
  :global(body) {
    --font-display: 'Bebas Neue', sans-serif;
    --font-body: 'Source Sans 3', system-ui, sans-serif;
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
    font-family: var(--font-body);
  }

  main.compact {
    width: 100%;
    min-height: 100vh;
    padding: 0.75rem 1.25rem;
    box-sizing: border-box;
  }

  .dashboard-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
  }

  .brand {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.75rem;
    letter-spacing: 0.02em;
  }

  .main-nav {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .nav-link {
    padding: 0.35rem 0.6rem;
    text-decoration: none;
    color: var(--text-muted);
    font-size: 0.9rem;
    border-radius: 4px;
  }
  .nav-link:hover { color: var(--text); background: rgba(255,255,255,0.06); }
  .nav-link.active { color: var(--text); font-weight: 600; background: var(--bg-elevated); }

  .stoplights {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .stoplight-btn {
    padding: 0.25rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 500;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--btn-bg);
    color: var(--text);
    cursor: pointer;
  }
  .stoplight-btn:hover { opacity: 0.9; }
  .stoplight-btn.status-ok { background: var(--badge-completed-bg); border-color: var(--status-ok); color: var(--status-ok); }
  .stoplight-btn.status-active { background: var(--badge-completed-bg); border-color: var(--status-ok); color: var(--status-ok); }
  .stoplight-btn.status-idle { background: var(--badge-pending-bg); border-color: var(--status-idle); color: var(--status-idle); }
  .stoplight-btn.status-unknown { background: var(--bg-elevated); border-color: var(--text-muted); color: var(--text-muted); }
  .stoplight-btn.status-uninitialized { background: var(--bg-elevated); border-color: var(--text-muted); color: var(--text-muted); }
  .stoplight-btn.status-error { background: rgba(248, 81, 73, 0.2); border-color: var(--status-error); color: var(--status-error); }


  section {
    margin-bottom: 1rem;
    padding: 0.75rem 1rem;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
  }

  .demo-warning-banner {
    margin: 0 0 0.5rem;
    padding: 0.5rem 0.75rem;
    background: rgba(210, 153, 34, 0.2);
    border: 1px solid var(--status-idle);
    border-radius: 6px;
    font-size: 0.85rem;
  }
  .demo-warning-banner .demo-warning-label { font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 0.5rem; }
  .demo-warning-banner code { padding: 0.15rem 0.35rem; background: var(--btn-bg); border-radius: 4px; font-size: 0.8em; }
  .track-diagram {
    padding: 0.5rem 0;
    overflow: auto;
  }
  .track-svg {
    width: 100%;
    min-width: 400px;
    height: auto;
  }
  .track-svg .station-node {
    fill: var(--bg-elevated);
    stroke: var(--border);
    stroke-width: 2;
  }
  .track-svg .station-node.station-clients { stroke: var(--text-muted); }
  .track-svg .station-node.station-hot { stroke: var(--bucket-hot); }
  .track-svg .station-node.station-warm { stroke: var(--bucket-warm); }
  .track-svg .station-node.station-cold { stroke: var(--bucket-cold); }
  .track-svg .station-node.station-offsite { stroke: var(--bucket-offsite); }
  .track-svg .station-label {
    fill: var(--text);
    font-family: var(--font-body);
    font-size: 11px;
    font-weight: 600;
  }
  .track-svg .station-count {
    fill: var(--text-muted);
    font-family: var(--font-body);
    font-size: 10px;
  }
  .track-svg .segment-flow {
    fill: var(--text-muted);
    font-family: var(--font-body);
    font-size: 9px;
  }
  .track-station-clickable {
    cursor: pointer;
  }
  .track-station-clickable:hover .station-node {
    filter: brightness(1.15);
  }
  .track-station-clickable:focus {
    outline: none;
  }
  .track-station-clickable:focus-visible .station-node {
    stroke-width: 3;
    stroke: var(--link);
  }

  .train-car-detail {
    margin-top: 1rem;
    padding: 1rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .train-car-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.75rem;
  }
  .train-car-title {
    font-size: 1rem;
    margin: 0;
    font-weight: 600;
  }
  .train-car-close {
    padding: 0.2rem 0.5rem;
    font-size: 1.25rem;
    line-height: 1;
    border: none;
    background: transparent;
    color: var(--text-muted);
    cursor: pointer;
  }
  .train-car-close:hover { color: var(--text); }
  .train-car-stats {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.25rem 1rem;
    font-size: 0.875rem;
    margin: 0 0 0.75rem;
  }
  .train-car-stats dt { color: var(--text-muted); }
  .train-car-sample-label { font-size: 0.8rem; color: var(--text-muted); margin: 0 0 0.25rem; }
  .train-car-sample { list-style: none; padding: 0; margin: 0 0 0.75rem; font-size: 0.8rem; }
  .train-car-sample li { padding: 0.2rem 0; border-bottom: 1px solid var(--border); }
  .train-car-path { display: inline-block; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: bottom; }
  .train-car-meta { color: var(--text-muted); margin-left: 0.35rem; }
  .train-car-link { font-size: 0.875rem; color: var(--link); }

  .stop-status {
    display: inline-block;
    padding: 0.15rem 0.4rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    border-radius: 4px;
  }
  .stop-status-ok { background: var(--badge-completed-bg); color: var(--badge-completed); }
  .stop-status-empty { background: var(--bg-elevated); color: var(--text-muted); }

  .stops-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 1rem;
    margin-top: 0.75rem;
  }
  .stop-card {
    padding: 1rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .stop-card-title {
    font-size: 1rem;
    margin: 0 0 0.5rem;
    font-weight: 600;
  }
  .stop-card-hot .stop-card-title { color: var(--bucket-hot); }
  .stop-card-warm .stop-card-title { color: var(--bucket-warm); }
  .stop-card-cold .stop-card-title { color: var(--bucket-cold); }
  .stop-card-offsite .stop-card-title { color: var(--bucket-offsite); }
  .stop-card-status { margin-bottom: 0.5rem; }
  .stop-card-stats {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.2rem 0.75rem;
    font-size: 0.875rem;
    margin: 0 0 0.5rem;
  }
  .stop-card-stats dt { color: var(--text-muted); }
  .stop-sample-label { font-size: 0.75rem; color: var(--text-muted); margin: 0 0 0.25rem; }
  .stop-sample-list { list-style: none; padding: 0; margin: 0; font-size: 0.8rem; }
  .stop-sample-list li { padding: 0.2rem 0; border-bottom: 1px solid var(--border); }
  .stop-path { display: inline-block; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: bottom; }
  .stop-meta { color: var(--text-muted); margin-left: 0.25rem; }

  .train-map-section {
    margin-bottom: 0.75rem;
    padding: 0.5rem 0.75rem;
  }

  .train-lines-section {
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--border);
  }
  .train-lines-grid {
    display: grid;
    grid-template-columns: minmax(8rem, auto) repeat(4, minmax(5rem, 1fr)) minmax(4rem, auto);
    gap: 0.25rem 0.75rem;
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
  }
  .train-lines-header {
    display: contents;
  }
  .train-lines-header .train-lines-cell {
    font-weight: 600;
    color: var(--text-muted);
  }
  .train-lines-row {
    display: contents;
  }
  .train-lines-row > .train-lines-cell {
    padding: 0.25rem 0;
    border-bottom: 1px solid var(--border);
  }
  .train-lines-row-cache {
    display: contents;
  }
  .train-lines-row-cache .train-lines-cache-badge {
    grid-column: 2 / -1;
  }
  .train-lines-cell {
    min-width: 0;
  }
  .train-lines-label {
    font-weight: 500;
  }
  .train-lines-notes {
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .train-lines-link {
    font-size: 0.85rem;
    color: var(--link);
  }

  .clients-summary {
    display: flex;
    gap: 1.5rem;
    margin-bottom: 0.75rem;
    padding: 0.5rem 0;
    font-size: 0.875rem;
  }
  .clients-summary-item { display: flex; gap: 0.35rem; }
  .clients-summary-label { color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }

  .setting-feedback { font-size: 0.85rem; color: var(--text-muted); margin-left: 0.5rem; }

  .depot-page {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem 1.25rem;
  }
  .depot-desc {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0 0 1rem;
  }
  .depot-subhead {
    font-family: var(--font-display);
    font-size: 1rem;
    letter-spacing: 0.02em;
    margin: 1rem 0 0.5rem;
  }
  .depot-grid {
    margin-top: 0.5rem;
  }
  .pipeline-by-tier {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 1rem;
    margin-bottom: 1rem;
  }
  .pipeline-tier {
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0.5rem 0.75rem;
    background: var(--bg);
  }
  .pipeline-tier-name {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    margin: 0 0 0.5rem;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid var(--border);
  }
  .pipeline-tier-list {
    font-size: 0.8rem;
  }
  .pipeline-pkg {
    padding: 0.25rem 0;
    border-bottom: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }
  .pipeline-pkg:last-child { border-bottom: none; }
  .pkg-path {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .pkg-meta {
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  .train-heading {
    font-family: var(--font-display);
    font-size: 1.15rem;
    letter-spacing: 0.02em;
    margin: 0 0 0.5rem;
  }

  h1 { font-size: 1.25rem; }
  h2 { font-size: 1rem; margin: 0 0 0.5rem; }

  .flow-desc {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0 0 1rem;
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
  .rules-legend {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 0 0 1rem;
    padding: 0.5rem 0.75rem;
    background: var(--bg-elevated);
    border-radius: 6px;
    border: 1px solid var(--border);
  }
  .rules-legend-item { margin: 0.25rem 0; line-height: 1.4; }
  .rules-legend-item:first-child { margin-top: 0; }
  .rules-legend-item:last-child { margin-bottom: 0; }
  .rules-legend code { font-size: 0.85em; padding: 0.1rem 0.3rem; background: var(--bg); border-radius: 3px; }
  .rules-grid-wrapper { min-height: 200px; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
  .rules-edit-bar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 1rem;
  }
  .rules-edit-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
  }
  .rules-edit-select {
    padding: 0.35rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg);
    color: var(--text);
    min-width: 10rem;
  }
  .rules-edit-btn {
    padding: 0.4rem 1rem;
    background: var(--accent, #238636);
    color: #fff;
    border: 1px solid var(--accent);
    border-radius: 6px;
    cursor: pointer;
  }
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 1rem;
  }
  .modal-content {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.5rem;
    max-width: 28rem;
    max-height: 90vh;
    overflow-y: auto;
  }
  .modal-title {
    margin: 0 0 1rem;
    font-size: 1.1rem;
  }

  .transitions-list { list-style: none; padding: 0; font-size: 0.875rem; }
  .transitions-list li { padding: 0.25rem 0; }

  .nav-link-icon {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }
  .gear-icon {
    flex-shrink: 0;
    opacity: 0.9;
  }
  .nav-link.active .gear-icon { opacity: 1; }
  .heading-icon {
    vertical-align: middle;
    margin-right: 0.4rem;
    opacity: 0.9;
  }
  .settings-heading { display: flex; align-items: center; }

  .settings-page .settings-grid {
    display: grid;
    gap: 1.5rem;
    margin-top: 0.75rem;
  }
  .setting-group {
    padding: 0.75rem 0;
    border-bottom: 1px solid var(--border);
  }
  .setting-group:last-of-type { border-bottom: none; }
  .setting-group-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text);
    margin: 0 0 0.5rem;
  }
  .setting-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .setting-label {
    font-size: 0.875rem;
    color: var(--text-muted);
    min-width: 8rem;
  }
  .setting-input {
    width: 5ch;
    text-align: right;
  }
  .setting-input-narrow { width: 4ch; }
  .setting-suffix {
    font-size: 0.875rem;
    color: var(--text-muted);
  }
  .setting-hint {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin: 0.35rem 0 0;
  }
  .setting-inline {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.875rem;
  }
  .setting-btn {
    margin-left: 0.5rem;
  }

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
