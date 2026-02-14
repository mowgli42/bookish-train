/**
 * Projections store: upcoming transitions from /api/v1/projections.
 * .svelte.js required for $state rune (Svelte 5).
 */
export function createProjectionsStore() {
  let days = $state(5)
  let transitions = $state([])
  let loading = $state(false)
  let error = $state(null)

  async function fetchProjections(daysParam = 5, secondsParam = null) {
    loading = true
    error = null
    try {
      const url = secondsParam != null
        ? `/api/v1/projections?days=${daysParam}&seconds=${secondsParam}`
        : `/api/v1/projections?days=${daysParam}`
      const r = await fetch(url)
      if (!r.ok) throw new Error(r.statusText)
      const data = await r.json()
      days = data.days ?? daysParam
      transitions = data.transitions || []
    } catch (e) {
      error = e.message
      transitions = []
    } finally {
      loading = false
    }
  }

  return {
    get days() { return days },
    get transitions() { return transitions },
    get loading() { return loading },
    get error() { return error },
    fetchProjections,
  }
}

export const projectionsStore = createProjectionsStore()
