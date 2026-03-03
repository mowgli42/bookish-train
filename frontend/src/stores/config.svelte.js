/**
 * Config store: rule sets and retention from /api/v1/config.
 * .svelte.js required for $state rune (Svelte 5).
 */
export function createConfigStore() {
  let retention = $state(null)
  let ruleSets = $state({})
  let loading = $state(false)
  let error = $state(null)

  let demoMode = $state(false)
  let unit = $state('days')

  async function fetchConfig() {
    loading = true
    error = null
    try {
      const r = await fetch('/api/v1/config')
      if (!r.ok) throw new Error(r.statusText)
      const data = await r.json()
      retention = data.retention || null
      ruleSets = data.rule_sets || {}
      demoMode = !!data.demo_mode
      unit = data.unit || 'days'
    } catch (e) {
      error = e.message
      retention = null
      ruleSets = {}
    } finally {
      loading = false
    }
  }

  async function patchConfig(ruleSetsUpdate) {
    loading = true
    error = null
    try {
      const r = await fetch('/api/v1/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rule_sets: ruleSetsUpdate }),
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || r.statusText)
      ruleSets = data.rule_sets || {}
      retention = data.retention || null
      demoMode = !!data.demo_mode
      unit = data.unit || 'days'
      return data
    } catch (e) {
      error = e.message
      throw e
    } finally {
      loading = false
    }
  }

  return {
    get retention() { return retention },
    get ruleSets() { return ruleSets },
    get demoMode() { return demoMode },
    get unit() { return unit },
    get loading() { return loading },
    get error() { return error },
    fetchConfig,
    patchConfig,
  }
}

export const configStore = createConfigStore()
