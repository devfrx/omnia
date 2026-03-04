/**
 * Composable providing a shared markdown-it renderer for the OMNIA UI.
 *
 * Initialises `markdown-it` once (singleton) with safe defaults and
 * returns a `renderMarkdown` function that converts raw markdown
 * strings into sanitised HTML.
 *
 * Code-highlight support is intentionally stubbed so highlight.js
 * can be wired in later without changing consumer call-sites.
 */

import MarkdownIt from 'markdown-it'

/**
 * Singleton markdown-it instance shared across all consumers.
 *
 * Configuration:
 * - `html: false`       — disables raw HTML pass-through for safety
 * - `linkify: true`     — auto-links bare URLs
 * - `typographer: true`  — smart quotes / dashes
 * - `breaks: true`       — treats single `\n` as `<br>`
 * - `highlight`          — placeholder returning a `<code>` block with
 *                          a language class so highlight.js can pick it up
 */
const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: true,
  highlight(str: string, lang: string): string {
    const langClass = lang ? ` class="language-${lang}"` : ''
    const escaped = str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
    return `<pre class="code-block"><code${langClass}>${escaped}</code></pre>`
  }
})

/**
 * Render a raw markdown string to HTML.
 *
 * @param raw - Markdown source text (may be empty / partial during streaming).
 * @returns Sanitised HTML string ready for `v-html`.
 */
export function renderMarkdown(raw: string): string {
  if (!raw) return ''
  return md.render(raw)
}
