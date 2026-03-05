/**
 * Composable for handling code block interactions (copy-to-clipboard).
 * Uses event delegation — attach the returned handler to the container
 * element that hosts v-html rendered markdown content.
 */
export function useCodeBlocks() {
  async function handleCodeBlockClick(event: MouseEvent): Promise<void> {
    // Find the closest .code-block-copy button from the click target
    const target = (event.target as HTMLElement).closest('.code-block-copy') as HTMLElement | null
    if (!target) return

    const encoded = target.getAttribute('data-code')
    if (!encoded) return

    try {
      const code = decodeURIComponent(escape(atob(encoded)))
      await navigator.clipboard.writeText(code)

      // Visual feedback
      const label = target.querySelector('.code-block-copy__label')
      const svg = target.querySelector('svg')
      if (label && svg) {
        const originalLabel = label.textContent
        const originalSvg = svg.outerHTML
        label.textContent = 'Copiato!'
        // Change to checkmark icon
        svg.outerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>'
        target.classList.add('code-block-copy--copied')

        setTimeout(() => {
          label.textContent = originalLabel
          const currentSvg = target.querySelector('svg')
          if (currentSvg) currentSvg.outerHTML = originalSvg
          target.classList.remove('code-block-copy--copied')
        }, 2000)
      }
    } catch (err) {
      console.error('[useCodeBlocks] Failed to copy code:', err)
    }
  }

  return { handleCodeBlockClick }
}
