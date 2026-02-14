/**
 * Packages store: list and refresh from catcher API.
 * .svelte.js required for $state rune (Svelte 5).
 */
export function createPackagesStore() {
  let packages = $state([])
  let loading = $state(false)
  let error = $state(null)

  async function fetchPackages() {
    loading = true
    error = null
    try {
      const r = await fetch('/api/v1/packages')
      if (!r.ok) throw new Error(r.statusText)
      packages = await r.json()
    } catch (e) {
      error = e.message
      packages = []
    } finally {
      loading = false
    }
  }

  return {
    get packages() { return packages },
    get loading() { return loading },
    get error() { return error },
    fetchPackages,
  }
}

export const packagesStore = createPackagesStore()
