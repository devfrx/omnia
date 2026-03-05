<script setup lang="ts">
/**
 * ConversationList.vue — List of conversation summaries for the sidebar.
 *
 * Features:
 * - "New Conversation" button at the top.
 * - Each item shows the title (or "Nuova conversazione"), a relative
 *   time-ago label, and the message count.
 * - Click selects; inline buttons allow delete and rename.
 * - Active item is visually highlighted.
 */
import { ref } from 'vue'

import type { ConversationSummary } from '../../types/chat'

defineProps<{
  /** Conversation summaries to display. */
  conversations: ConversationSummary[]
  /** ID of the currently active conversation (null = none). */
  activeId: string | null
}>()

const emit = defineEmits<{
  select: [id: string]
  create: []
  delete: [id: string]
  rename: [id: string, title: string]
  'open-file': [id: string]
}>()

/** ID of the conversation currently being renamed (inline edit). */
const renamingId = ref<string | null>(null)

/** Temporary value while the user edits the title. */
const renameValue = ref('')

/**
 * Compute a human-readable "time ago" string from an ISO timestamp.
 *
 * @param iso - ISO-8601 date string.
 * @returns A short relative label (e.g. "3 min fa", "2h fa", "ieri").
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

/** Enter inline-rename mode for a conversation. */
function startRename(conv: ConversationSummary): void {
  renamingId.value = conv.id
  renameValue.value = conv.title ?? ''
}

/** Confirm the inline rename and emit. */
function confirmRename(id: string): void {
  const trimmed = renameValue.value.trim()
  if (trimmed) {
    emit('rename', id, trimmed)
  }
  renamingId.value = null
}

/** Cancel the inline rename. */
function cancelRename(): void {
  renamingId.value = null
}
</script>

<template>
  <div class="conv-list">
    <!-- New conversation -->
    <button class="conv-list__new" @click="emit('create')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
      Nuova chat
    </button>

    <!-- Conversation items -->
    <div v-for="conv in conversations" :key="conv.id" class="conv-item"
      :class="{ 'conv-item--active': conv.id === activeId }" @click="emit('select', conv.id)">
      <!-- Normal display -->
      <template v-if="renamingId !== conv.id">
        <span class="conv-item__title">{{ conv.title ?? 'Nuova conversazione' }}</span>
        <span class="conv-item__meta">
          <span>{{ conv.message_count }} msg</span>
          <span class="conv-item__time">{{ timeAgo(conv.updated_at) }}</span>
        </span>
      </template>

      <!-- Inline rename -->
      <template v-else>
        <input v-model="renameValue" class="conv-item__rename-input" autofocus
          @keydown.enter.stop="confirmRename(conv.id)" @keydown.escape.stop="cancelRename" @click.stop />
      </template>

      <!-- Action buttons -->
      <div class="conv-item__actions" @click.stop>
        <button v-if="renamingId !== conv.id" class="conv-item__action" aria-label="Apri cartella"
          title="Apri nel file manager" @click="emit('open-file', conv.id)">
          <!-- Folder icon -->
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
          </svg>
        </button>
        <button v-if="renamingId !== conv.id" class="conv-item__action" aria-label="Rinomina conversazione"
          title="Rinomina" @click="startRename(conv)">
          <!-- Pencil icon -->
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
          </svg>
        </button>
        <button v-if="renamingId === conv.id" class="conv-item__action" aria-label="Conferma" title="Conferma"
          @click="confirmRename(conv.id)">
          <!-- Check icon -->
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </button>
        <button class="conv-item__action conv-item__action--danger" aria-label="Elimina conversazione" title="Elimina"
          @click="emit('delete', conv.id)">
          <!-- Trash icon -->
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
  overflow-y: auto;
  flex: 1;
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
}

.conv-list__new:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
}

/* ------------------------------------------------ Conversation item */
.conv-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  position: relative;
  transition: background var(--transition-fast);
}

.conv-item:hover {
  background: rgba(255, 255, 255, 0.05);
}

.conv-item--active {
  background: var(--accent-dim);
  border-left: 2px solid var(--accent);
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
