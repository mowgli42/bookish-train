/**
 * Buckets store: summary by tier from /api/v1/buckets.
 * .svelte.js required for $state rune (Svelte 5).
 */
export function createBucketsStore() {
  let buckets = $state([])
  let loading = $state(false)
  let error = $state(null)

  async function fetchBuckets() {
    loading = true
    error = null
    try {
      const r = await fetch('/api/v1/buckets')
      if (!r.ok) throw new Error(r.statusText)
      const data = await r.json()
      buckets = data.buckets || []
    } catch (e) {
      error = e.message
      buckets = []
    } finally {
      loading = false
    }
  }

  return {
    get buckets() { return buckets },
    get loading() { return loading },
    get error() { return error },
    fetchBuckets,
  }
}

export const bucketsStore = createBucketsStore()
