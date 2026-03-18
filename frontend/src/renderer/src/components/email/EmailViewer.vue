<script setup lang="ts">
import { useEmailStore } from '../../stores/email'

const emailStore = useEmailStore()

async function handleArchive(): Promise<void> {
    if (!emailStore.currentEmail) return
    await emailStore.archiveEmail(
        emailStore.currentEmail.uid,
        emailStore.currentFolder,
    )
}

async function handleMarkRead(read: boolean): Promise<void> {
    if (!emailStore.currentEmail) return
    await emailStore.markRead(
        emailStore.currentEmail.uid,
        read,
        emailStore.currentFolder,
    )
}
</script>

<template>
    <div v-if="emailStore.currentEmail" class="email-viewer">
        <div class="email-viewer__header">
            <div class="email-viewer__subject">
                {{ emailStore.currentEmail.subject }}
            </div>
            <div class="email-viewer__meta">
                <span><b>Da:</b> {{ emailStore.currentEmail.from }}</span>
                <span><b>A:</b> {{ emailStore.currentEmail.to }}</span>
                <span v-if="emailStore.currentEmail.cc">
                    <b>Cc:</b> {{ emailStore.currentEmail.cc }}
                </span>
                <span>{{ emailStore.currentEmail.date }}</span>
            </div>
            <div class="email-viewer__actions">
                <button @click="handleMarkRead(!emailStore.currentEmail?.is_read)">
                    {{ emailStore.currentEmail.is_read ? 'Segna non letta' : 'Segna letta' }}
                </button>
                <button class="btn-archive" @click="handleArchive">Archivia</button>
                <button @click="emailStore.clearCurrentEmail()">Chiudi</button>
            </div>
        </div>
        <div class="email-viewer__body">{{ emailStore.currentEmail.body }}</div>
    </div>
</template>

<style scoped>
.email-viewer {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.email-viewer__subject {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-primary);
}

.email-viewer__meta {
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 0.8rem;
    color: var(--text-secondary);
}

.email-viewer__actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.email-viewer__actions button {
    padding: 4px 10px;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: var(--surface-2);
    cursor: pointer;
    font-size: 0.8rem;
    color: var(--text-primary);
    transition: background var(--transition-fast) ease, color var(--transition-fast) ease;
}

.email-viewer__actions button:hover {
    background: var(--surface-hover);
}

.email-viewer__actions button:focus-visible {
    box-shadow: var(--focus-ring-shadow);
}

.btn-archive {
    border-color: var(--accent);
    color: var(--accent);
}

.email-viewer__body {
    white-space: pre-wrap;
    font-size: 0.875rem;
    line-height: 1.6;
    color: var(--text-primary);
    background: var(--surface-2);
    padding: 16px;
    border-radius: 6px;
}
</style>
