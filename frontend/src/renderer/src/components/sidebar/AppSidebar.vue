<script setup lang="ts">
/**
 * AppSidebar.vue — Collapsible sidebar wrapping navigation and conversations.
 *
 * Layout:
 * - Top: navigation links (Settings)
 * - Middle: {@link ConversationList} (scrollable)
 * - Toggle button to collapse/expand (0 ↔ 260 px)
 *
 * The component owns no data — it reads from the Pinia chat store
 * and delegates mutations back through events / store actions.
 */
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useChatStore } from '../../stores/chat'
import { useUIStore } from '../../stores/ui'
import { useModal } from '../../composables/useModal'
import { api } from '../../services/api'
import ConversationList from './ConversationList.vue'
import CalendarWidget from '../calendar/CalendarWidget.vue'
import TaskWidget from '../tasks/TaskWidget.vue'

const chatStore = useChatStore()
const uiStore = useUIStore()
const router = useRouter()
const { confirm } = useModal()

/** Whether the sidebar is expanded (wired to central UI store). */
const isOpen = computed(() => uiStore.sidebarOpen)

/** Toggle collapsed state via central UI store. */
function toggle(): void {
  uiStore.toggleSidebar()
}

/** Load conversations on mount so the sidebar is populated immediately. */
onMounted(() => {
  chatStore.loadConversations().catch(console.error)
})

// -----------------------------------------------------------------------
// Conversation actions (delegated to store)
// -----------------------------------------------------------------------

/** Select an existing conversation and navigate to hybrid mode. */
async function onSelect(id: string): Promise<void> {
  try {
    await chatStore.loadConversation(id)
  } catch (err) {
    // Graceful degradation — log the failure and stay on the current view
    // rather than leaving the UI in an inconsistent state.
    console.error(`[AppSidebar] Failed to load conversation ${id}:`, err)
    return
  }
  if (router.currentRoute.value.name !== 'hybrid') {
    await router.push({ name: 'hybrid' })
  }
}

/** Create a new conversation and navigate to hybrid mode. */
async function onCreate(): Promise<void> {
  await chatStore.createConversation()
  if (router.currentRoute.value.name !== 'hybrid') {
    await router.push({ name: 'hybrid' })
  }
}

/** Delete a conversation. */
async function onDelete(id: string): Promise<void> {
  await chatStore.deleteConversation(id)
}

/** Delete ALL conversations (with confirmation). */
let deleteAllPending = false
async function onDeleteAll(): Promise<void> {
  if (deleteAllPending) return
  deleteAllPending = true
  try {
    const confirmed = await confirm({
      title: 'Elimina tutte le conversazioni',
      message: 'Eliminare tutte le conversazioni? Questa azione è irreversibile.',
      type: 'danger',
      confirmText: 'Elimina tutto',
    })
    if (!confirmed) return
    await chatStore.deleteAllConversations()
  } catch (err) {
    console.error('[AppSidebar] Failed to delete all conversations:', err)
  } finally {
    deleteAllPending = false
  }
}

/** Rename a conversation. */
async function onRename(id: string, title: string): Promise<void> {
  await chatStore.renameConversation(id, title)
}

/** Open the conversation file in the system file manager. */
async function onOpenFile(id: string): Promise<void> {
  try {
    const { path } = await api.getConversationFilePath(id)
    window.electron.fileOps.showInFolder(path)
  } catch (err) {
    console.error(`[AppSidebar] Failed to open file for conversation ${id}:`, err)
  }
}
</script>

<template>
  <aside class="sidebar" :class="{ 'sidebar--collapsed': !isOpen }">
    <!-- Dot-grid texture overlay (CSS-only depth layer) -->
    <div class="sidebar__texture" aria-hidden="true" />

    <!-- Animated sweep line along the top edge -->
    <span class="sidebar__top-line" aria-hidden="true" />

    <!-- Primary navigation — icons always visible, labels hidden when collapsed -->
    <nav class="sidebar__nav" aria-label="Navigazione principale">
      <router-link to="/settings" class="sidebar__link" active-class="sidebar__link--active" title="Impostazioni">
        <span class="sidebar__link-bar" aria-hidden="true" />
        <span class="sidebar__link-icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1.08-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1.08 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1.08 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.604.852.997 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1.08z" />
          </svg>
        </span>
        <span class="sidebar__link-label">Impostazioni</span>
      </router-link>

      <router-link to="/assistant" class="sidebar__link" active-class="sidebar__link--active" title="Assistente">
        <span class="sidebar__link-bar" aria-hidden="true" />
        <span class="sidebar__link-icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="4" />
          </svg>
        </span>
        <span class="sidebar__link-label">Assistente</span>
      </router-link>

      <router-link to="/hybrid" class="sidebar__link" active-class="sidebar__link--active" title="Ibrido">
        <span class="sidebar__link-bar" aria-hidden="true" />
        <span class="sidebar__link-icon" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="8" r="6" />
            <path d="M4 20h16" opacity="0.5" />
          </svg>
        </span>
        <span class="sidebar__link-label">Ibrido</span>
      </router-link>
    </nav>

    <!-- Calendar widget — shows today's events and next upcoming -->
    <CalendarWidget :collapsed="!isOpen" />

    <!-- Task widget — shows active autonomous tasks -->
    <TaskWidget :collapsed="!isOpen" />

    <!-- Conversations section — only shown when expanded -->
    <div v-show="isOpen" class="sidebar__conversations">
      <!-- Section divider with micro uppercase label -->
      <div class="sidebar__section-label">
        <span>Conversazioni</span>
      </div>

      <!-- Virtualised conversation list -->
      <ConversationList :conversations="chatStore.conversations" :active-id="chatStore.currentConversation?.id ?? null"
        :streaming-id="chatStore.streamingConversationId" @select="onSelect" @create="onCreate" @delete="onDelete"
        @delete-all="onDeleteAll" @rename="onRename" @open-file="onOpenFile" />
    </div>

    <!-- Toggle button — bottom of sidebar, circular chevron -->
    <button class="sidebar__toggle" :aria-label="isOpen ? 'Chiudi sidebar' : 'Apri sidebar'" :aria-expanded="isOpen"
      @click="toggle">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round">
        <polyline v-if="isOpen" points="15 18 9 12 15 6" />
        <polyline v-else points="9 18 15 12 9 6" />
      </svg>
    </button>
  </aside>
</template>

<style scoped>
/* ═══════════════════════════════════════════════════════════
   AppSidebar — Collapsible navigation sidebar
   ═══════════════════════════════════════════════════════════ */

/* ------------------------------------------------- Root */
.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--surface-1);
  border-right: 1px solid var(--border);
  box-shadow: 1px 0 12px rgba(0, 0, 0, 0.25);
  transition:
    width var(--duration-moderate) var(--ease-out-expo),
    min-width var(--duration-moderate) var(--ease-out-expo);
  overflow: hidden;
  position: relative;
  z-index: var(--z-sticky);
}

.sidebar--collapsed {
  width: var(--sidebar-collapsed);
  min-width: var(--sidebar-collapsed);
}

/* ------------------------------------------------- Subtle texture overlay */
.sidebar__texture {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: var(--z-base);
  background-image: radial-gradient(circle,
      rgba(255, 255, 255, 0.015) 1px,
      transparent 1px);
  background-size: 20px 20px;
  opacity: 0.25;
  -webkit-mask-image: linear-gradient(to bottom,
      transparent 0%,
      rgba(0, 0, 0, 0.3) 15%,
      rgba(0, 0, 0, 0.3) 85%,
      transparent 100%);
  mask-image: linear-gradient(to bottom,
      transparent 0%,
      rgba(0, 0, 0, 0.3) 15%,
      rgba(0, 0, 0, 0.3) 85%,
      transparent 100%);
}

/* ------------------------------------------------- Animated top border sweep
   A soft gold highlight that scans left → right → left slowly */
.sidebar__top-line {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: var(--space-px);
  z-index: var(--z-raised);
  pointer-events: none;
  background: linear-gradient(90deg,
      transparent 0%,
      transparent 10%,
      var(--accent) 50%,
      transparent 90%,
      transparent 100%);
  background-size: 300% 100%;
  background-position: -100% 0;
  opacity: var(--opacity-soft);
  animation: topLineSweep 8s ease-in-out infinite;
}

@keyframes topLineSweep {
  0% {
    background-position: -100% 0;
  }

  50% {
    background-position: 100% 0;
  }

  100% {
    background-position: -100% 0;
  }
}

/* ------------------------------------------------- Navigation */
.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-3) var(--space-2) var(--space-2);
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  transition: padding var(--duration-normal) ease;
}

.sidebar--collapsed .sidebar__nav {
  padding: var(--space-1) 0 var(--space-2);
  align-items: center;
}

/* Pill-style nav link */
.sidebar__link {
  display: flex;
  align-items: center;
  gap: var(--space-2-5);
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  letter-spacing: 0.01em;
  color: var(--text-secondary);
  text-decoration: none;
  position: relative;
  overflow: hidden;
  transition:
    background 120ms ease,
    color 120ms ease;
}

/* Center icons when collapsed */
.sidebar--collapsed .sidebar__link {
  justify-content: center;
  gap: 0;
  padding: var(--space-2) 0;
  border-radius: var(--radius-full);
  width: 34px;
  height: 34px;
  margin: 0 auto;
}

/* Hide the gold left-bar indicator when collapsed — too narrow to look good */
.sidebar--collapsed .sidebar__link-bar {
  opacity: 0;
}

/* Compact circular highlight for active link when collapsed */
.sidebar--collapsed .sidebar__link--active {
  background: var(--accent-dim);
  box-shadow: 0 0 12px rgba(201, 168, 76, 0.1);
  border-radius: var(--radius-full);
}

/* Gold left-bar indicator — transparent by default */
.sidebar__link-bar {
  position: absolute;
  left: 0;
  top: 22%;
  bottom: 22%;
  width: 3px;
  border-radius: 0 2px 2px 0;
  background: transparent;
  transition:
    background var(--transition-fast),
    box-shadow var(--transition-fast),
    opacity var(--transition-fast);
}

.sidebar__link-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  opacity: var(--opacity-soft);
  transition: opacity var(--transition-fast), filter var(--transition-fast);
}

/* Text label — collapses out with width + opacity */
.sidebar__link-label {
  white-space: nowrap;
  overflow: hidden;
  max-width: 160px;
  opacity: 1;
  transition:
    opacity var(--transition-normal),
    max-width var(--transition-normal);
}

.sidebar--collapsed .sidebar__link-label {
  opacity: 0;
  max-width: 0;
  pointer-events: none;
}

.sidebar__link:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.sidebar__link:hover .sidebar__link-icon {
  opacity: 1;
}

.sidebar__link:active {
  transform: scale(0.97);
}

/* Active state — gold left bar + subtle highlight */
.sidebar__link--active {
  color: var(--text-primary);
  background: var(--surface-selected);
}

.sidebar__link--active .sidebar__link-bar {
  background: var(--accent);
  box-shadow: 0 0 8px rgba(201, 168, 76, 0.3);
  width: 3px;
}

.sidebar__link--active .sidebar__link-icon {
  opacity: 1;
  color: var(--accent);
}

/* ------------------------------------------------- Conversations section */
.sidebar__conversations {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  position: relative;
  z-index: 1;
  animation: contentReveal 0.22s ease-out;
}

@keyframes contentReveal {
  from {
    opacity: 0;
    transform: translateX(-5px);
  }

  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* ------------------------------------------------- Section label
   Micro uppercase text + trailing fade line */
.sidebar__section-label {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 14px var(--space-1);
  font-size: var(--text-2xs);
  font-weight: var(--weight-bold);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-muted);
  flex-shrink: 0;
}

.sidebar__section-label::after {
  content: '';
  flex: 1;
  height: var(--space-px);
  background: linear-gradient(90deg, var(--border) 0%, transparent 100%);
}

/* ------------------------------------------------- Toggle button (bottom-center, circular) */
.sidebar__toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: var(--surface-2);
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
  margin: var(--space-2) auto var(--space-3);
  position: relative;
  z-index: 1;
  transition:
    color 120ms ease,
    border-color 120ms ease,
    background 120ms ease,
    transform 80ms ease;
}

.sidebar__toggle:hover {
  color: var(--text-primary);
  border-color: var(--border-hover);
  background: var(--surface-3);
}

.sidebar__toggle:active {
  transform: scale(0.9);
}

.sidebar__toggle:focus-visible {
  box-shadow: var(--focus-ring-shadow);
}

/* ------------------------------------------------- Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .sidebar__top-line {
    animation: none;
    background: var(--accent-border);
    background-size: 100% 100%;
    opacity: 0.35;
  }

  .sidebar__conversations {
    animation: none;
  }

  .sidebar,
  .sidebar__nav,
  .sidebar__link,
  .sidebar__link-bar,
  .sidebar__link-icon,
  .sidebar__link-label,
  .sidebar__toggle {
    transition: none;
  }
}
</style>
