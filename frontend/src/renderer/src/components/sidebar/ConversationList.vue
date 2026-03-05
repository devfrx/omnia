<script setup lang="ts">
/**
 * ConversationList.vue — Virtualised list of conversation summaries.
 *
 * Features:
 * - "New Conversation" button at the top.
 * - Virtual scrolling for 1000+ conversations.
 * - Keyboard navigation (arrow keys, Enter, Escape).
 * - ARIA roles for accessibility.
 */
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'

import type { ConversationSummary } from '../../types/chat'

const props = defineProps<{
  /** Conversation summaries to display. */
  conversations: ConversationSummary[]
  /** ID of the currently active conversation (null = none). */
  activeId: string | null
  /** ID of the conversation currently being streamed (null = none). */
  streamingId: string | null
}>()

const emit = defineEmits<{
  select: [id: string]
  create: []
  delete: [id: string]
  rename: [id: string, title: string]
  'open-file': [id: string]
}>()

// -----------------------------------------------------------------------
// Virtual scroll state
// -----------------------------------------------------------------------

/** Height of each conversation item in pixels. */
const ITEM_HEIGHT = 52
/** Extra items rendered above/below the visible area. */
const BUFFER = 5

const scrollContainer = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const containerHeight = ref(0)

const totalHeight = computed(() => props.conversations.length * ITEM_HEIGHT)

const startIndex = computed(() =>
  Math.max(0, Math.floor(scrollTop.value / ITEM_HEIGHT) - BUFFER)
)
const endIndex = computed(() =>
  Math.min(
    props.conversations.length,
    Math.ceil((scrollTop.value + containerHeight.value) / ITEM_HEIGHT) + BUFFER
  )
)

const visibleItems = computed(() =>
  props.conversations.slice(startIndex.value, endIndex.value).map((conv, i) => ({
    conv,
    index: startIndex.value + i,
    offset: (startIndex.value + i) * ITEM_HEIGHT
  }))
)

function onScroll(): void {
  if (scrollContainer.value) {
    scrollTop.value = scrollContainer.value.scrollTop
  }
}

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
  if (scrollContainer.value) {
    containerHeight.value = scrollContainer.value.clientHeight
    resizeObserver = new ResizeObserver(([entry]) => {
      containerHeight.value = entry.contentRect.height
    })
    resizeObserver.observe(scrollContainer.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
})

// -----------------------------------------------------------------------
// Inline rename
// -----------------------------------------------------------------------

/** ID of the conversation currently being renamed (inline edit). */
const renamingId = ref<string | null>(null)
/** Temporary value while the user edits the title. */
const renameValue = ref('')

function startRename(conv: ConversationSummary): void {
  renamingId.value = conv.id
  renameValue.value = conv.title ?? ''
}

function confirmRename(id: string): void {
  const trimmed = renameValue.value.trim()
  if (trimmed) emit('rename', id, trimmed)
  renamingId.value = null
}

function cancelRename(): void {
  renamingId.value = null
}

// -----------------------------------------------------------------------
// Keyboard navigation (Item 7)
// -----------------------------------------------------------------------

/** Index of the currently focused conversation (-1 = none). */
const focusedIndex = ref(-1)

function handleListKeydown(event: KeyboardEvent): void {
  const len = props.conversations.length
  if (len === 0) return

  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      focusedIndex.value = Math.min(focusedIndex.value + 1, len - 1)
      scrollToIndex(focusedIndex.value)
      break
    case 'ArrowUp':
      event.preventDefault()
      focusedIndex.value = Math.max(focusedIndex.value - 1, 0)
      scrollToIndex(focusedIndex.value)
      break
    case 'Enter':
      event.preventDefault()
      if (focusedIndex.value >= 0 && focusedIndex.value < len) {
        emit('select', props.conversations[focusedIndex.value].id)
      }
      break
    case 'Home':
      event.preventDefault()
      focusedIndex.value = 0
      scrollToIndex(0)
      break
    case 'End':
      event.preventDefault()
      focusedIndex.value = len - 1
      scrollToIndex(len - 1)
      break
  }
}

function scrollToIndex(index: number): void {
  if (!scrollContainer.value) return
  const itemTop = index * ITEM_HEIGHT
  const itemBottom = itemTop + ITEM_HEIGHT
  const viewTop = scrollContainer.value.scrollTop
  const viewBottom = viewTop + containerHeight.value
  if (itemTop < viewTop) {
    scrollContainer.value.scrollTop = itemTop
  } else if (itemBottom > viewBottom) {
    scrollContainer.value.scrollTop = itemBottom - containerHeight.value
  }
}

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

/**
 * Compute a human-readable "time ago" string from an ISO timestamp.
 */
function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'adesso'
  if (mins < 60) return `${mins} min fa`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h fa`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'ieri'
  if (days < 30) return `${days}g fa`
  return new Date(iso).toLocaleDateString()
}
</script>

<template>
  <div class="conv-list">
    <!-- New conversation -->
    <button class="conv-list__new" aria-label="Nuova chat" @click="emit('create')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
      Nuova chat
    </button>

    <!-- Virtual-scrolled conversation items -->
    <div ref="scrollContainer" class="conv-list__scroller" role="listbox" aria-label="Conversazioni" tabindex="0"
      @scroll="onScroll" @keydown="handleListKeydown">
      <div class="conv-list__spacer" :style="{ height: totalHeight + 'px' }">
        <div v-for="{ conv, index, offset } in visibleItems" :key="conv.id" class="conv-item" :class="{
          'conv-item--active': conv.id === activeId,
          'conv-item--focused': index === focusedIndex
        }" role="option" :aria-selected="conv.id === activeId" :style="{ transform: `translateY(${offset}px)` }"
          @click="emit('select', conv.id)">
          <!-- Normal display -->
          <template v-if="renamingId !== conv.id">
            <span class="conv-item__title">
              <span v-if="conv.id === streamingId" class="conv-item__streaming-dot" aria-label="Generazione in corso" />
              {{ conv.title ?? 'Nuova conversazione' }}
            </span>
            <span class="conv-item__meta">
              <span>{{ conv.message_count }} msg</span>
              <span class="conv-item__time">{{ timeAgo(conv.updated_at) }}</span>
            </span>
          </template>

          <!-- Inline rename -->
          <template v-else>
            <input v-model="renameValue" class="conv-item__rename-input" autofocus aria-label="Rinomina conversazione"
              @keydown.enter.stop="confirmRename(conv.id)" @keydown.escape.stop="cancelRename" @click.stop />
          </template>

          <!-- Action buttons -->
          <div class="conv-item__actions" @click.stop>
            <button v-if="renamingId !== conv.id" class="conv-item__action" aria-label="Apri cartella"
              title="Apri nel file manager" @click="emit('open-file', conv.id)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
              </svg>
            </button>
            <button v-if="renamingId !== conv.id" class="conv-item__action" aria-label="Rinomina conversazione"
              title="Rinomina" @click="startRename(conv)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
              </svg>
            </button>
            <button v-if="renamingId === conv.id" class="conv-item__action" aria-label="Conferma" title="Conferma"
              @click="confirmRename(conv.id)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </button>
            <button class="conv-item__action conv-item__action--danger" aria-label="Elimina conversazione"
              title="Elimina" @click="emit('delete', conv.id)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6l-1 14H6L5 6" />
                <path d="M10 11v6" />
                <path d="M14 11v6" />
                <path d="M9 6V4h6v2" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <p v-if="conversations.length === 0" class="conv-list__empty">
      Nessuna conversazione
    </p>
  </div>
</template>

<style scoped>
.conv-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px;
  flex: 1;
  min-height: 0;
}

.conv-list__scroller {
  flex: 1;
  overflow-y: auto;
  position: relative;
  outline: none;
}

.conv-list__scroller:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
  border-radius: var(--radius-md);
}

.conv-list__spacer {
  position: relative;
  width: 100%;
}

/* ------------------------------------------------ New chat button */
.conv-list__new {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 6px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.82rem;
  cursor: pointer;
  transition: background var(--transition-normal), color var(--transition-normal);
  flex-shrink: 0;
}

.conv-list__new:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
}

.conv-list__new:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

/* ------------------------------------------------ Conversation item */
.conv-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  position: absolute;
  left: 0;
  right: 0;
  height: 52px;
  transition: background var(--transition-fast);
}

.conv-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.conv-item--active {
  background: var(--accent-dim);
  border-left: 2px solid var(--accent);
}

.conv-item--focused {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}

.conv-item__title {
  font-size: 0.84rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-right: 40px;
}

.conv-item__meta {
  display: flex;
  gap: 8px;
  font-size: 0.72rem;
  color: var(--text-secondary);
  opacity: 0.7;
}

.conv-item__time {
  margin-left: auto;
}

/* ------------------------------------------------ Streaming indicator */
.conv-item__streaming-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  margin-right: 6px;
  vertical-align: middle;
  flex-shrink: 0;
  animation: streamingPulse 1.5s ease-in-out infinite;
  box-shadow: 0 0 6px rgba(201, 168, 76, 0.4);
}

@keyframes streamingPulse {

  0%,
  100% {
    opacity: 1;
    box-shadow: 0 0 6px rgba(201, 168, 76, 0.4);
  }

  50% {
    opacity: 0.4;
    box-shadow: 0 0 12px rgba(201, 168, 76, 0.6);
  }
}

/* ------------------------------------------------ Inline rename */
.conv-item__rename-input {
  width: 100%;
  padding: 4px 6px;
  background: var(--bg-input);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 0.84rem;
  outline: none;
}

/* ------------------------------------------------ Action buttons */
.conv-item__actions {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.15s;
}

.conv-item:hover .conv-item__actions {
  opacity: 1;
}

.conv-item__action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.conv-item__action:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
}

.conv-item__action:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

.conv-item__action--danger:hover {
  background: var(--danger-hover);
  color: var(--danger);
}

/* ------------------------------------------------ Empty state */
.conv-list__empty {
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-secondary);
  opacity: 0.5;
  margin-top: 2rem;
}
</style>
