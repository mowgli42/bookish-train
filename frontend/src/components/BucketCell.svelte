<script>
  let { row } = $props()
  const bucket = $derived(row?.bucket || 'hot')
</script>

<span class="bucket-badge bucket-{bucket}">{bucket}</span>
