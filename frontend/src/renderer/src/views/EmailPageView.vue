<script setup lang="ts">
/**
 * EmailPageView.vue — Vista principale Email Assistant.
 *
 * Layout a tre colonne: sidebar cartelle | InboxList | EmailViewer.
 * Le notifiche EMAIL_RECEIVED arrivano tramite useEventsWebSocket.ts (singleton).
 */
import { onMounted } from 'vue'
import { useEmailStore } from '../stores/email'
import InboxList from '../components/email/InboxList.vue'
import EmailViewer from '../components/email/EmailViewer.vue'

const emailStore = useEmailStore()

onMounted(async () => {
    await emailStore.fetchInbox()
    await emailStore.fetchFolders()
})
</script>

<template>
    <div class="email-page">
        <aside class="email-page__folders">
            <div class="email-page__folder-title">Cartelle</div>
            <ul class="email-page__folder-list">
                <li v-for="folder in emailStore.folders" :key="folder"
                    :class="{ active: emailStore.currentFolder === folder }" @click="emailStore.fetchInbox(folder)">
                    {{ folder }}
                </li>
            </ul>
        </aside>

        <section class="email-page__inbox">
            <InboxList />
        </section>

        <section class="email-page__viewer">
            <EmailViewer v-if="emailStore.currentEmail" />
            <div v-else class="email-page__empty">
                Seleziona un'email per leggerla
            </div>
        </section>
    </div>
</template>

<style scoped>
.email-page {
    display: grid;
    grid-template-columns: 180px 1fr 1.6fr;
    height: 100%;
    width: 100%;
    overflow: hidden;
    background: var(--surface-0);
    color: var(--text-primary);
}

.email-page__folders {
    border-right: 1px solid var(--border);
    padding: 12px 0;
    overflow-y: auto;
}

.email-page__folder-title {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-secondary);
    padding: 0 12px 8px;
}

.email-page__folder-list {
    list-style: none;
    margin: 0;
    padding: 0;
}

.email-page__folder-list li {
    padding: 6px 12px;
    cursor: pointer;
    font-size: 0.875rem;
    color: var(--text-primary);
    border-radius: 4px;
    margin: 0 4px;
    transition: background var(--transition-fast) ease;
}

.email-page__folder-list li:hover,
.email-page__folder-list li.active {
    background: var(--surface-hover);
}

.email-page__inbox {
    border-right: 1px solid var(--border);
    overflow-y: auto;
}

.email-page__viewer {
    overflow-y: auto;
    padding: 20px;
}

.email-page__empty {
    padding: 32px;
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.9rem;
}
</style>
