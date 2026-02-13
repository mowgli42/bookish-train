/**
 * Config store: retention rule set from /api/v1/config.
 * .svelte.js required for $state rune (Svelte 5).
 */
export function createConfigStore() {
  let retention = $state(null)
  let loading = $state(false)
  let error = $state(null)

  async function fetchConfig() {
    loading = true
    error = null
    try {
      const r = await fetch('/api/v1/config')
      if (!r.ok) throw new Error(r.statusText)
      const data = await r.json()
      retention = data.retention || null
    } catch (e) {
      error = e.message
      retention = null
    } finally {
      loading = false
    }
  }

  return {
    get retention() { return retention },
    get loading() { return loading },
    get error() { return error },
    fetchConfig,
  }
}

export const configStore = createConfigStore()
