/**
 * Toaster store: show transient feedback messages.
 * Use for API success/error feedback (e.g. rules updated, error saving).
 */
export function createToasterStore() {
  let toasts = $state([])

  function show(message, type = 'info') {
    const id = crypto.randomUUID()
    toasts = [...toasts, { id, message, type }]
    setTimeout(() => {
      toasts = toasts.filter((t) => t.id !== id)
    }, 4000)
  }

  function dismiss(id) {
    toasts = toasts.filter((t) => t.id !== id)
  }

  return {
    get toasts() {
      return toasts
    },
    show,
    success: (msg) => show(msg, 'success'),
    error: (msg) => show(msg, 'error'),
    dismiss,
  }
}

export const toasterStore = createToasterStore()
