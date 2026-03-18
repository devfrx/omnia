<script setup lang="ts">
import { useEmailStore } from '../../stores/email'

const emailStore = useEmailStore()
</script>

<template>
    <div class="inbox-list">
        <div class="inbox-list__toolbar">
            <span class="inbox-list__count">
                {{ emailStore.inbox.length }} email
                <span v-if="emailStore.unreadCount > 0" class="inbox-list__unread">
                    · {{ emailStore.unreadCount }} non lette
                </span>
            </span>
            <button class="inbox-list__refresh" :disabled="emailStore.loading"
                @click="emailStore.fetchInbox(emailStore.currentFolder)">
                ↻
            </button>
        </div>

        <div v-if="emailStore.loading" class="inbox-list__loading">Caricamento…</div>
        <div v-else-if="emailStore.error" class="inbox-list__error">
            {{ emailStore.error }}
        </div>
        <div v-else-if="emailStore.inbox.length === 0" class="inbox-list__empty">
            Nessuna email
        </div>

        <ul v-else class="inbox-list__items">
            <li v-for="mail in emailStore.inbox" :key="mail.uid" class="inbox-list__item"
                :class="{ unread: !mail.is_read }" @click="emailStore.fetchEmail(mail.uid, emailStore.currentFolder)">
                <div class="inbox-list__item-from">{{ mail.from }}</div>
                <div class="inbox-list__item-subject">{{ mail.subject }}</div>
                <div class="inbox-list__item-date">{{ mail.date }}</div>
            </li>
        </ul>
    </div>
</template>

<style scoped>
.inbox-list {
    display: flex;
    flex-direction: column;
    height: 100%;
}

.inbox-list__toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border);
}

.inbox-list__count {
    font-size: 0.8rem;
    color: var(--text-secondary);
}

.inbox-list__unread {
    color: var(--accent);
    font-weight: 600;
}

.inbox-list__refresh {
    background: none;
    border: none;
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 1rem;
}

.inbox-list__loading,
.inbox-list__error,
.inbox-list__empty {
    padding: 24px;
    text-align: center;
    font-size: 0.875rem;
    color: var(--text-secondary);
}

.inbox-list__error {
    color: var(--danger);
}

.inbox-list__items {
    list-style: none;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    flex: 1;
}

.inbox-list__item {
    padding: 10px 12px;
    cursor: pointer;
    border-bottom: 1px solid var(--border);
    transition: background var(--transition-fast) ease;
}

.inbox-list__item:hover {
    background: var(--surface-hover);
}

.inbox-list__item.unread .inbox-list__item-subject {
    font-weight: 700;
}

.inbox-list__item-from {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 2px;
}

.inbox-list__item-subject {
    font-size: 0.875rem;
    color: var(--text-primary);
}

.inbox-list__item-date {
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: 2px;
}
</style>
