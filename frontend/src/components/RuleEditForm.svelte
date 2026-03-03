<script>
  /**
   * Form to edit a single rule's stops or cache_seconds.
   * Props: rule (from configStore.ruleSets[ptype]), packageType, isDemo, onSave, onCancel
   */
  let { rule = {}, packageType = '', isDemo = false, onSave, onCancel } = $props()

  const waitKey = $derived(isDemo ? 'wait_seconds' : 'wait_days')
  const BUCKET_ORDER = ['hot', 'warm', 'cold', 'offsite']

  // Local draft - deep copy of rule for form binding
  let stops = $state({})
  let cacheSeconds = $state(86400)
  let replicateToAll = $state(false)

  $effect(() => {
    if (!rule || !packageType) return
    if (rule.cache_seconds != null) {
      cacheSeconds = rule.cache_seconds
      return
    }
    const s = rule.stops || {}
    const defWait = (name) => (name === 'hot' ? 7 : name === 'warm' ? 30 : name === 'cold' ? 365 : 2555)
    stops = Object.fromEntries(
      BUCKET_ORDER.map((name) => {
        const existing = s[name] || {}
        const d = defWait(name)
        return [
          name,
          {
            enabled: existing.enabled !== false,
            wait_days: existing.wait_days ?? d,
            wait_seconds: existing.wait_seconds ?? d,
            never_delete: name === 'offsite' ? !!existing.never_delete : undefined,
          },
        ]
      })
    )
    replicateToAll = !!rule.replicate_to_all
  })

  let saving = $state(false)
  let errorMsg = $state(null)

  async function submit() {
    errorMsg = null
    saving = true
    try {
      let payload = {}
      if (rule?.cache_seconds != null) {
        payload = { cache_seconds: Math.max(0, parseInt(String(cacheSeconds), 10) || 0) }
      } else {
        const builtStops = {}
        let prevEnabled = true
        for (const name of BUCKET_ORDER) {
          const s = stops[name] || {}
          const enabled = s.enabled !== false
          if (enabled && !prevEnabled) {
            errorMsg = `${name} enabled requires previous tier to be enabled`
            return
          }
          prevEnabled = enabled
          const val = isDemo ? s.wait_seconds : s.wait_days
          const wait = enabled ? Math.max(1, parseInt(String(val), 10) || 1) : 0
          builtStops[name] = { enabled }
          if (enabled) {
            if (name === 'offsite' && s.never_delete) {
              builtStops[name].never_delete = true
            } else {
              builtStops[name][waitKey] = wait
              if (name === 'offsite') builtStops[name].never_delete = false
            }
          }
        }
        payload = { stops: builtStops, replicate_to_all: replicateToAll }
      }
      await onSave?.({ [packageType]: payload })
      onCancel?.()
    } catch (e) {
      errorMsg = e?.message || 'Failed to save'
    } finally {
      saving = false
    }
  }
</script>

<div class="rule-edit-form">
  {#if rule?.cache_seconds != null}
    <label class="form-row" for="cache-ttl-input">
      <span class="form-label">Cache TTL (seconds)</span>
      <input id="cache-ttl-input" type="number" bind:value={cacheSeconds} min="1" max="86400" class="form-input" />
    </label>
  {:else}
    {#each BUCKET_ORDER as name}
      {@const s = stops[name] || {}}
      <div class="form-row form-row-stop">
        <span class="form-label">{name}</span>
        <div class="form-stop-controls">
          <label class="form-check">
            <input type="checkbox" bind:checked={s.enabled} />
            <span>enabled</span>
          </label>
          {#if s.enabled}
            {#if name === 'offsite'}
              <label class="form-check">
                <input type="checkbox" bind:checked={s.never_delete} />
                <span>never delete</span>
              </label>
              {#if !s.never_delete}
                {#if isDemo}
                  <input type="number" bind:value={s.wait_seconds} min="1" class="form-input form-input-narrow" />
                {:else}
                  <input type="number" bind:value={s.wait_days} min="1" class="form-input form-input-narrow" />
                {/if}
                <span class="form-suffix">{isDemo ? 's' : 'd'}</span>
              {/if}
            {:else}
              {#if isDemo}
                <input type="number" bind:value={s.wait_seconds} min="1" class="form-input form-input-narrow" />
              {:else}
                <input type="number" bind:value={s.wait_days} min="1" class="form-input form-input-narrow" />
              {/if}
              <span class="form-suffix">{isDemo ? 's' : 'd'}</span>
            {/if}
          {/if}
        </div>
      </div>
    {/each}
    {#if packageType === 'business_data'}
      <label class="form-row form-check">
        <input type="checkbox" bind:checked={replicateToAll} />
        <span>Replicate to all tiers</span>
      </label>
    {/if}
  {/if}

  {#if errorMsg}
    <p class="form-error" role="alert">{errorMsg}</p>
  {/if}

  <div class="form-actions">
    <button type="button" class="form-btn form-btn-secondary" onclick={onCancel} disabled={saving}>Cancel</button>
    <button type="button" class="form-btn form-btn-primary" onclick={submit} disabled={saving}>
      {saving ? 'Saving…' : 'Save'}
    </button>
  </div>
</div>

<style>
  .rule-edit-form {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 0.5rem 0;
  }
  .form-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .form-row-stop {
    flex-wrap: wrap;
  }
  .form-label {
    flex: 0 0 5rem;
    text-transform: capitalize;
    font-weight: 500;
  }
  .form-stop-controls {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  .form-input {
    width: 6rem;
    padding: 0.35rem 0.5rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg);
    color: var(--text);
  }
  .form-input-narrow {
    width: 4rem;
  }
  .form-suffix {
    font-size: 0.85em;
    color: var(--muted);
  }
  .form-check {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    cursor: pointer;
  }
  .form-check input {
    cursor: pointer;
  }
  .form-error {
    color: var(--danger, #f85149);
    font-size: 0.9em;
  }
  .form-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .form-btn {
    padding: 0.4rem 1rem;
    border-radius: 6px;
    font-size: 0.9rem;
    cursor: pointer;
    border: 1px solid var(--border);
  }
  .form-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
  .form-btn-primary {
    background: var(--accent, #238636);
    color: #fff;
    border-color: var(--accent);
  }
  .form-btn-secondary {
    background: transparent;
    color: var(--text);
  }
</style>
