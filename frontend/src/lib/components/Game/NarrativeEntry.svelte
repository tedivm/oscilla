<script lang="ts">
  import type { NarrativeEntry } from "$lib/stores/gameSession.js";
  import { renderMarkup } from "$lib/utils/markup.js";

  interface Props {
    entry: NarrativeEntry;
  }

  let { entry }: Props = $props();
</script>

<!--
  Each entry gets a CSS fade-in animation on mount.
  The parent uses entry.id as the {#each} key so that already-rendered
  entries are not re-mounted (and therefore do not re-animate).
  Entries recovered from crash-recovery (gameSession.init) get the same
  animation but are already visible by the time the user sees them, so
  the 300ms fade is imperceptible in practice.
-->
<p class="narrative-entry">{@html renderMarkup(entry.text)}</p>

<style>
  .narrative-entry {
    margin: 0;
    line-height: 1.7;
    animation: fade-in 300ms ease-in-out both;
  }

  @keyframes fade-in {
    from {
      opacity: 0;
      transform: translateY(4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
