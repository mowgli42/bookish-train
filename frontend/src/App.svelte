<script>
  import { jobsStore } from './stores/jobs.svelte.js'
  import { sourcesStore } from './stores/sources.svelte.js'

  let mounted = $state(false)
  $effect(() => {
    if (mounted) {
      jobsStore.fetchJobs()
      sourcesStore.fetchSources()
    }
  })

  function refreshAll() {
    jobsStore.fetchJobs()
    sourcesStore.fetchSources()
  }
</script>

<svelte:window onload={() => (mounted = true)} />

<main>
  <h1>Edge Backup Dashboard</h1>
  <p class="subtitle">Transfer progress and inventory (read-only).</p>

  <nav aria-label="Dashboard sections">
    <a href="#jobs">Jobs</a>
    <a href="#sources">Sources</a>
  </nav>

  <!-- Jobs section -->
  <section id="jobs" aria-labelledby="jobs-heading">
    <h2 id="jobs-heading">Jobs</h2>
    <button
      type="button"
      onclick={refreshAll}
      disabled={jobsStore.loading}
      aria-busy={jobsStore.loading}
      aria-label="Refresh jobs and sources"
    >
      {jobsStore.loading ? 'Loading…' : 'Refresh'}
    </button>
    {#if jobsStore.error}
      <p class="error" role="alert">{jobsStore.error}</p>
    {/if}
    <ul class="job-list">
      {#each jobsStore.jobs as job (job.job_id)}
        <li>
          <strong>{job.job_id}</strong> — {job.source_id} / {job.path}
          <span class="badge badge-{job.status}" aria-label="Status: {job.status}">
            {job.status}
          </span>
          <span class="progress">{job.progress_percent}%</span>
        </li>
      {/each}
    </ul>
    {#if !jobsStore.loading && jobsStore.jobs.length === 0 && !jobsStore.error}
      <p class="empty">No jobs yet. Ingest via POST /api/v1/ingest.</p>
    {/if}
  </section>

  <!-- Sources section -->
  <section id="sources" aria-labelledby="sources-heading">
    <h2 id="sources-heading">Sources</h2>
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
  /* IxDF dark theme: affordances, signifiers, contrast */
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
    --error: #f85149;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    min-height: 100vh;
  }

  main {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    max-width: 60rem;
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
  }

  nav a {
    margin-right: 1rem;
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

  /* Status badges — clear signifiers (IxDF) */
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

  .badge-pending {
    background: var(--badge-pending-bg);
    color: var(--badge-pending);
  }

  .badge-in_progress {
    background: var(--badge-in_progress-bg);
    color: var(--badge-in_progress);
  }

  .badge-completed {
    background: var(--badge-completed-bg);
    color: var(--badge-completed);
  }

  .badge-failed {
    background: var(--badge-failed-bg);
    color: var(--badge-failed);
  }

  .progress {
    margin-left: 0.5rem;
    color: var(--text-muted);
  }

  .job-list,
  .source-list {
    list-style: none;
    padding: 0;
  }

  .job-list li,
  .source-list li {
    padding: 0.6rem 0;
    border-bottom: 1px solid var(--border);
  }

  .job-list li:last-child,
  .source-list li:last-child {
    border-bottom: none;
  }

  .source-id {
    font-weight: 600;
    color: var(--text);
  }

  .source-label {
    color: var(--text-muted);
  }

  .last-seen {
    font-size: 0.875rem;
    color: var(--text-muted);
    display: block;
    margin-top: 0.25rem;
  }

  .error {
    color: var(--error);
  }

  .empty,
  .loading {
    color: var(--text-muted);
  }
</style>
