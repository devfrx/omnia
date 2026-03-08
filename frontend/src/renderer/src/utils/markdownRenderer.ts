/**
 * Lightweight markdown-to-HTML renderer for OMNIA assistant responses.
 *
 * Supports: bold, italic, inline code, fenced code blocks, headers,
 * unordered/ordered lists, blockquotes, links, paragraphs.
 *
 * Security: HTML entities are escaped BEFORE any markdown transforms
 * to prevent XSS injection.
 */

/** Escape HTML entities to prevent XSS. */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** Render inline markdown (bold, italic, code, links). */
function renderInline(text: string): string {
  // Inline code (must come before bold/italic to protect backtick content)
  text = text.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
  // Bold
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  // Italic (asterisk)
  text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  // Italic (underscore — word boundaries only)
  text = text.replace(/(?<!\w)_([^_]+)_(?!\w)/g, '<em>$1</em>')
  // Links
  text = text.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
  )
  return text
}

/**
 * Convert a markdown string to sanitised HTML.
 *
 * The function is intentionally kept simple and dependency-free.
 * It processes block-level structures first, then applies inline rendering.
 */
export function renderMarkdown(source: string): string {
  if (!source) return ''

  // 1. Escape all HTML entities first (XSS protection)
  const escaped = escapeHtml(source)

  // 2. Extract fenced code blocks into placeholders before any processing
  const codeBlocks: string[] = []
  const withPlaceholders = escaped.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    (_match, lang: string, code: string) => {
      const idx = codeBlocks.length
      const langAttr = lang ? ` data-lang="${lang}"` : ''
      const langLabel = lang
        ? `<span class="code-block__lang">${lang}</span>`
        : ''
      codeBlocks.push(
        `${langLabel}<pre class="code-block"${langAttr}><code>${code.replace(
          /\n$/,
          ''
        )}</code></pre>`
      )
      return `\x00CODEBLOCK_${idx}\x00`
    }
  )

  // 3. Process block-level structures line by line
  const lines = withPlaceholders.split('\n')
  const html: string[] = []
  let inList: 'ul' | 'ol' | null = null
  let inBlockquote = false
  let paragraphBuffer: string[] = []

  const flushParagraph = (): void => {
    if (paragraphBuffer.length > 0) {
      html.push(`<p>${renderInline(paragraphBuffer.join(' '))}</p>`)
      paragraphBuffer = []
    }
  }

  const closeList = (): void => {
    if (inList) {
      html.push(inList === 'ul' ? '</ul>' : '</ol>')
      inList = null
    }
  }

  const closeBlockquote = (): void => {
    if (inBlockquote) {
      html.push('</blockquote>')
      inBlockquote = false
    }
  }

  for (const line of lines) {
    // Code block placeholder — emit as-is
    const cbMatch = line.match(/^\x00CODEBLOCK_(\d+)\x00$/)
    if (cbMatch) {
      flushParagraph()
      closeList()
      closeBlockquote()
      html.push(codeBlocks[parseInt(cbMatch[1], 10)])
      continue
    }

    // Headers
    const headerMatch = line.match(/^(#{1,3})\s+(.+)$/)
    if (headerMatch) {
      flushParagraph()
      closeList()
      closeBlockquote()
      const level = headerMatch[1].length
      html.push(
        `<h${level} class="md-h${level}">${renderInline(headerMatch[2])}</h${level}>`
      )
      continue
    }

    // Blockquote
    const bqMatch = line.match(/^&gt;\s?(.*)$/)
    if (bqMatch) {
      flushParagraph()
      closeList()
      if (!inBlockquote) {
        html.push('<blockquote>')
        inBlockquote = true
      }
      html.push(renderInline(bqMatch[1]))
      continue
    } else if (inBlockquote) {
      closeBlockquote()
    }

    // Unordered list
    const ulMatch = line.match(/^[\s]*[-*]\s+(.+)$/)
    if (ulMatch) {
      flushParagraph()
      if (inList !== 'ul') {
        closeList()
        html.push('<ul>')
        inList = 'ul'
      }
      html.push(`<li>${renderInline(ulMatch[1])}</li>`)
      continue
    }

    // Ordered list
    const olMatch = line.match(/^[\s]*\d+\.\s+(.+)$/)
    if (olMatch) {
      flushParagraph()
      if (inList !== 'ol') {
        closeList()
        html.push('<ol>')
        inList = 'ol'
      }
      html.push(`<li>${renderInline(olMatch[1])}</li>`)
      continue
    }

    // Close list if current line is not a list item
    if (inList) closeList()

    // Empty line → flush paragraph
    if (line.trim() === '') {
      flushParagraph()
      continue
    }

    // Normal text — accumulate into paragraph
    paragraphBuffer.push(line)
  }

  // Close any remaining open structures
  flushParagraph()
  closeList()
  closeBlockquote()

  return html.join('\n')
}
