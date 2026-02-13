/**
 * Sources store: list from catcher API.
 * .svelte.js required for $state rune (Svelte 5).
 */
export function createSourcesStore() {
  let sources = $state([])
  let loading = $state(false)
  let error = $state(null)

  async function fetchSources() {
    loading = true
    error = null
    try {
      const r = await fetch('/api/v1/sources')
      if (!r.ok) throw new Error(r.statusText)
      sources = await r.json()
    } catch (e) {
      error = e.message
      sources = []
    } finally {
      loading = false
    }
  }

  return {
    get sources() { return sources },
    get loading() { return loading },
    get error() { return error },
    fetchSources,
  }
}

export const sourcesStore = createSourcesStore()
