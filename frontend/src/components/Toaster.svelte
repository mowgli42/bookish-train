<script>
  import { toasterStore } from '../stores/toaster.svelte.js'
</script>

<div class="toaster" role="status" aria-live="polite">
  {#each toasterStore.toasts as toast (toast.id)}
    <div class="toast toast-{toast.type}" onclick={() => toasterStore.dismiss(toast.id)}>
      {toast.message}
    </div>
  {/each}
</div>

<style>
  .toaster {
    position: fixed;
    bottom: 1.5rem;
    right: 1.5rem;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 24rem;
  }
  .toast {
    padding: 0.75rem 1rem;
    border-radius: 8px;
    font-size: 0.875rem;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    border: 1px solid;
  }
  .toast-success {
    background: #1a4d2e;
    border-color: #3fb950;
    color: #e6edf3;
  }
  .toast-error {
    background: #5d1f1a;
    border-color: #f85149;
    color: #e6edf3;
  }
  .toast-info {
    background: #161b22;
    border-color: #30363d;
    color: #e6edf3;
  }
</style>
