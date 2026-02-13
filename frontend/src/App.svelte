<script>
  import { jobsStore } from './stores/jobs.svelte.js'
  import { sourcesStore } from './stores/sources.svelte.js'
  import { bucketsStore } from './stores/buckets.svelte.js'
  import { configStore } from './stores/config.svelte.js'
  import { projectionsStore } from './stores/projections.svelte.js'

  let mounted = $state(false)
  let projectionDays = $state(5)

  $effect(() => {
    if (mounted) {
      jobsStore.fetchJobs()
      sourcesStore.fetchSources()
      bucketsStore.fetchBuckets()
      configStore.fetchConfig()
      projectionsStore.fetchProjections(projectionDays)
    }
  })

  function refreshAll() {
    jobsStore.fetchJobs()
    sourcesStore.fetchSources()
    bucketsStore.fetchBuckets()
    configStore.fetchConfig()
    projectionsStore.fetchProjections(projectionDays)
  }

  function formatBytes(n) {
    if (n === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(n) / Math.log(k))
    return `${parseFloat((n / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
  }

  const BUCKET_LABELS = { hot: 'Hot', warm: 'Warm', cold: 'Cold', offsite: 'Offsite' }
</script>

<svelte:window onload={() => (mounted = true)} />

<main>
  <h1>Edge Backup Dashboard</h1>
  <p class="subtitle">
    Data flow: Sources → Catcher → Buckets. Rule sets control retention; projections show what will move.
  </p>

  <nav aria-label="Dashboard sections">
    <a href="#flow">Data Flow</a>
    <a href="#buckets">Buckets</a>
    <a href="#rules">Rule Set</a>
    <a href="#projections">Projections</a>
    <a href="#jobs">Jobs</a>
    <a href="#sources">Sources</a>
  </nav>

  <!-- Data flow: conceptual diagram -->
  <section id="flow" aria-labelledby="flow-heading">
    <h2 id="flow-heading">Data Flow</h2>
    <div class="flow-diagram">
      <div class="flow-node sources">
        <strong>Sources (Edge)</strong>
        <p>Clients watch folders, package data, POST to catcher. No durable data on edge.</p>
      </div>
      <span class="flow-arrow">→</span>
      <div class="flow-node catcher">
        <strong>Catcher</strong>
        <p>Receives ingest, applies rule sets, assigns buckets. Tracks metadata.</p>
      </div>
      <span class="flow-arrow">→</span>
      <div class="flow-node buckets-flow">
        <strong>Buckets</strong>
        <p>Hot → Warm → Cold → Offsite. Data moves by age per retention rules.</p>
      </div>
    </div>
  </section>

  <!-- Buckets: per-tier counts -->
  <section id="buckets" aria-labelledby="buckets-heading">
    <h2 id="buckets-heading">Buckets</h2>
    <button
      type="button"
      onclick={refreshAll}
      disabled={bucketsStore.loading}
      aria-busy={bucketsStore.loading}
      aria-label="Refresh all data"
    >
      {bucketsStore.loading ? 'Loading…' : 'Refresh'}
    </button>
    {#if bucketsStore.error}
      <p class="error" role="alert">{bucketsStore.error}</p>
    {/if}
    <div class="bucket-cards">
      {#each bucketsStore.buckets as bucket (bucket.name)}
        <div class="bucket-card bucket-{bucket.name}">
          <h3>{BUCKET_LABELS[bucket.name] ?? bucket.name}</h3>
          <p class="count">{bucket.count} items</p>
          <p class="size">{formatBytes(bucket.total_bytes)}</p>
          {#if bucket.sample?.length}
            <ul class="sample-list">
              {#each bucket.sample as item}
                <li>
                  <code>{item.path}</code>
                  <span class="age">({item.age_days}d)</span>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {/each}
    </div>
    {#if !bucketsStore.loading && bucketsStore.buckets.length === 0}
      <p class="empty">No buckets yet. Ingest via POST /api/v1/ingest.</p>
    {/if}
  </section>

  <!-- Rule set: retention config -->
  <section id="rules" aria-labelledby="rules-heading">
    <h2 id="rules-heading">Retention Rule Set</h2>
    {#if configStore.loading}
      <p class="loading" aria-live="polite">Loading config…</p>
    {:else if configStore.error}
      <p class="error" role="alert">{configStore.error}</p>
    {:else if configStore.retention}
      <div class="retention-view">
        <p class="rule-summary">
          Hot {configStore.retention.hot_days}d → Warm {configStore.retention.warm_days}d → Cold {configStore.retention.cold_days}d → Offsite {configStore.retention.offsite_days}d
        </p>
        <p class="rule-note">
          Operational metadata: {configStore.retention.operational_days} days.
        </p>
      </div>
    {:else}
      <p class="empty">No retention config available.</p>
    {/if}
  </section>

  <!-- Projections: what will transition -->
  <section id="projections" aria-labelledby="projections-heading">
    <h2 id="projections-heading">Projections</h2>
    <p class="projection-desc">
      In the next
      <input type="number" bind:value={projectionDays} min="1" max="365" aria-label="Days" />
      days, which files will transition to a colder bucket?
    </p>
    <button
      type="button"
      onclick={() => projectionsStore.fetchProjections(projectionDays)}
      disabled={projectionsStore.loading}
      aria-label="Refresh projections"
    >
      {projectionsStore.loading ? 'Loading…' : 'Update'}
    </button>
    {#if projectionsStore.error}
      <p class="error" role="alert">{projectionsStore.error}</p>
    {/if}
    {#if projectionsStore.transitions.length > 0}
      <ul class="transitions-list">
        {#each projectionsStore.transitions as t}
          <li>
            <strong>{t.bucket_from} → {t.bucket_to}</strong>:
            {t.count} file{t.count === 1 ? '' : 's'}
            {#if t.jobs?.length}
              <span class="job-ids">({t.jobs.slice(0, 3).join(', ')}{t.jobs.length > 3 ? '…' : ''})</span>
            {/if}
          </li>
        {/each}
      </ul>
    {:else if !projectionsStore.loading}
      <p class="empty">No transitions projected in the next {projectionDays} days.</p>
    {/if}
  </section>

  <!-- Jobs -->
  <section id="jobs" aria-labelledby="jobs-heading">
    <h2 id="jobs-heading">Jobs</h2>
    {#if jobsStore.error}
      <p class="error" role="alert">{jobsStore.error}</p>
    {/if}
    <ul class="job-list">
      {#each jobsStore.jobs as job (job.job_id)}
        <li>
          <strong>{job.job_id}</strong> — {job.source_id} / <code>{job.path}</code>
          <span class="badge badge-{job.status}" aria-label="Status: {job.status}">{job.status}</span>
          <span class="badge bucket-badge bucket-{job.bucket ?? job.tier ?? 'hot'}" aria-label="Bucket: {job.bucket ?? job.tier}">{job.bucket ?? job.tier ?? 'hot'}</span>
          <span class="meta">{job.age_days ?? 0}d · {job.progress_percent}%</span>
        </li>
      {/each}
    </ul>
    {#if !jobsStore.loading && jobsStore.jobs.length === 0 && !jobsStore.error}
      <p class="empty">No jobs yet. Ingest via POST /api/v1/ingest.</p>
    {/if}
  </section>

  <!-- Sources -->
  <section id="sources" aria-labelledby="sources-heading">
    <h2 id="sources-heading">Sources (Streams)</h2>
    {#if sourcesStore.loading}
      <p class="loading" aria-live="polite">Loading sources…</p>
    {:else if sourcesStore.error}
      <p class="error" role="alert">{sourcesStore.error}</p>
    {:else}
      <ul class="source-list">
        {#each sourcesStore.sources as source (source.source_id)}
          <li>
            <span class="source-id">{source.source_id}</span>
            {#if source.label}
              <span class="source-label">— {source.label}</span>
            {/if}
            {#if source.last_seen_at}
              <time datetime={source.last_seen_at} class="last-seen">
                last seen {new Date(source.last_seen_at).toLocaleString()}
              </time>
            {/if}
          </li>
        {/each}
      </ul>
      {#if sourcesStore.sources.length === 0}
        <p class="empty">No sources registered.</p>
      {/if}
    {/if}
  </section>
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
    --btn-hover: #30363d;
    --badge-pending: #9e6a03;
    --badge-pending-bg: #3d2e00;
    --badge-in_progress: #539bf5;
    --badge-in_progress-bg: #1c3d6a;
    --badge-completed: #3fb950;
    --badge-completed-bg: #1a4d2e;
    --badge-failed: #f85149;
    --badge-failed-bg: #5d1f1a;
    --bucket-hot: #3fb950;
    --bucket-warm: #539bf5;
    --bucket-cold: #a371f7;
    --bucket-offsite: #8b949e;
    --error: #f85149;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    min-height: 100vh;
  }

  main {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    max-width: 70rem;
    margin: 0 auto;
    padding: 1.5rem;
    color: var(--text);
  }

  .subtitle {
    color: var(--text-muted);
    margin-top: -0.5rem;
  }

  nav {
    margin: 1rem 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  nav a {
    color: var(--link);
    text-decoration: underline;
  }

  nav a:hover {
    color: var(--link-hover);
    text-decoration: none;
  }

  section {
    margin-bottom: 2rem;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1rem 1.25rem;
  }

  h1 { color: var(--text); }
  h2 {
    font-size: 1.25rem;
    margin-bottom: 0.5rem;
    color: var(--text);
  }

  h3 {
    font-size: 1rem;
    margin: 0 0 0.5rem;
  }

  button {
    padding: 0.5rem 1rem;
    font-size: 1rem;
    cursor: pointer;
    border: 1px solid var(--btn-border);
    border-radius: 6px;
    background: var(--btn-bg);
    color: var(--text);
  }

  button:hover:not(:disabled) {
    background: var(--btn-hover);
    border-color: var(--text-muted);
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }

  .flow-diagram {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.75rem;
    padding: 1rem 0;
  }

  .flow-node {
    flex: 1;
    min-width: 10rem;
    padding: 1rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
  }

  .flow-node p {
    margin: 0.5rem 0 0;
    font-size: 0.875rem;
    color: var(--text-muted);
  }

  .flow-arrow {
    color: var(--text-muted);
    font-size: 1.5rem;
  }

  .bucket-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
    gap: 1rem;
    margin-top: 1rem;
  }

  .bucket-card {
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--bg);
  }

  .bucket-card.bucket-hot { border-left: 4px solid var(--bucket-hot); }
  .bucket-card.bucket-warm { border-left: 4px solid var(--bucket-warm); }
  .bucket-card.bucket-cold { border-left: 4px solid var(--bucket-cold); }
  .bucket-card.bucket-offsite { border-left: 4px solid var(--bucket-offsite); }

  .bucket-card .count, .bucket-card .size {
    font-size: 0.875rem;
    color: var(--text-muted);
    margin: 0.25rem 0;
  }

  .sample-list {
    list-style: none;
    padding: 0;
    margin: 0.5rem 0 0;
    font-size: 0.75rem;
  }

  .sample-list li {
    padding: 0.25rem 0;
    border-bottom: none;
  }

  .sample-list code { font-size: 0.7rem; }
  .sample-list .age { color: var(--text-muted); }

  .retention-view .rule-summary {
    font-family: ui-monospace, monospace;
    font-size: 0.9rem;
  }

  .retention-view .rule-note {
    font-size: 0.875rem;
    color: var(--text-muted);
    margin-top: 0.5rem;
  }

  .projection-desc {
    margin-bottom: 0.5rem;
  }

  .projection-desc input {
    width: 4ch;
    padding: 0.25rem;
    font-size: 1rem;
    background: var(--btn-bg);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--text);
  }

  .transitions-list {
    list-style: none;
    padding: 0;
  }

  .transitions-list li {
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border);
  }

  .transitions-list .job-ids {
    font-size: 0.8rem;
    color: var(--text-muted);
  }

  .badge {
    display: inline-block;
    padding: 0.2rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-radius: 4px;
    margin-left: 0.5rem;
  }

  .badge-pending { background: var(--badge-pending-bg); color: var(--badge-pending); }
  .badge-in_progress { background: var(--badge-in_progress-bg); color: var(--badge-in_progress); }
  .badge-completed { background: var(--badge-completed-bg); color: var(--badge-completed); }
  .badge-failed { background: var(--badge-failed-bg); color: var(--badge-failed); }

  .bucket-badge.bucket-hot { background: #1a4d2e; color: var(--bucket-hot); }
  .bucket-badge.bucket-warm { background: #1c3d6a; color: var(--bucket-warm); }
  .bucket-badge.bucket-cold { background: #2d1f5d; color: var(--bucket-cold); }
  .bucket-badge.bucket-offsite { background: #21262d; color: var(--bucket-offsite); }

  .meta { margin-left: 0.5rem; color: var(--text-muted); font-size: 0.875rem; }

  .job-list, .source-list { list-style: none; padding: 0; }

  .job-list li, .source-list li {
    padding: 0.6rem 0;
    border-bottom: 1px solid var(--border);
  }

  .job-list li:last-child, .source-list li:last-child { border-bottom: none; }

  .job-list code { font-size: 0.85rem; }

  .source-id { font-weight: 600; color: var(--text); }
  .source-label { color: var(--text-muted); }
  .last-seen {
    font-size: 0.875rem;
    color: var(--text-muted);
    display: block;
    margin-top: 0.25rem;
  }

  .error { color: var(--error); }
  .empty, .loading { color: var(--text-muted); }
</style>
