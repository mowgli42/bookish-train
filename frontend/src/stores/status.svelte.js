/**
 * Status store: component status from /api/v1/status.
 * .svelte.js required for $state rune (Svelte 5).
 */
export function createStatusStore() {
  let status = $state(null)
  let loading = $state(false)
  let error = $state(null)

  async function fetchStatus() {
    loading = true
    error = null
    try {
      const r = await fetch('/api/v1/status')
      if (!r.ok) throw new Error(r.statusText)
      status = await r.json()
    } catch (e) {
      error = e.message
      status = null
    } finally {
      loading = false
    }
  }

  return {
    get status() { return status },
    get loading() { return loading },
    get error() { return error },
    fetchStatus,
  }
}

export const statusStore = createStatusStore()
