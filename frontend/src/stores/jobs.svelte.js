/**
 * Jobs store: list and refresh from catcher API.
 * .svelte.js required for $state rune (Svelte 5).
 */
export function createJobsStore() {
  let jobs = $state([])
  let loading = $state(false)
  let error = $state(null)

  async function fetchJobs() {
    loading = true
    error = null
    try {
      const r = await fetch('/api/v1/jobs')
      if (!r.ok) throw new Error(r.statusText)
      jobs = await r.json()
    } catch (e) {
      error = e.message
      jobs = []
    } finally {
      loading = false
    }
  }

  return {
    get jobs() { return jobs },
    get loading() { return loading },
    get error() { return error },
    fetchJobs,
  }
}

export const jobsStore = createJobsStore()
