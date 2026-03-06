<script setup lang="ts">
/**
 * ModalContainer.vue — Global modal renderer.
 *
 * Mount once in App.vue. It reads the singleton state from
 * `useModal` and renders the appropriate dialog when visible.
 * Handles focus trap, keyboard shortcuts, and animated transitions.
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import { useModal } from '../composables/useModal'

const { state, close } = useModal()

const cardRef = ref<HTMLElement | null>(null)

// ── Focus management ──────────────────────────────────────────

/** Auto-focus the primary action button when the modal opens. */
watch(
    () => state.visible,
    async (visible) => {
        if (!visible) return
        await nextTick()
        const btn = cardRef.value?.querySelector<HTMLElement>(
            '.modal__btn--confirm, .modal__btn--ok',
        )
        btn?.focus()
    },
)

/** Trap focus within the dialog and handle Enter / Escape. */
function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') {
        e.preventDefault()
        close(false)
        return
    }

    if (e.key === 'Enter') {
        e.preventDefault()
        const focused = document.activeElement as HTMLElement | null
        if (focused?.classList.contains('modal__btn')) {
            focused.click()
        } else {
            close(true)
        }
        return
    }

    // Focus trap
    if (e.key === 'Tab') {
        const focusable = cardRef.value?.querySelectorAll<HTMLElement>(
            'button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        )
        if (!focusable?.length) return

        const first = focusable[0]
        const last = focusable[focusable.length - 1]

        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault()
            last.focus()
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault()
            first.focus()
        }
    }
}

const isAlert = computed(() => state.type === 'alert')

onUnmounted(() => {
    if (state.visible) close(false)
})
</script>

<template>
    <Teleport to="body">
        <Transition name="modal">
            <div v-if="state.visible" class="modal-overlay" @click.self="state.type !== 'danger' && close(false)"
                @keydown="handleKeydown">
                <div ref="cardRef" class="modal-card" role="dialog" aria-modal="true"
                    :aria-label="state.title || 'Dialogo'" aria-describedby="modal-desc">
                    <h3 v-if="state.title" class="modal-card__title">{{ state.title }}</h3>
                    <p id="modal-desc" class="modal-card__message">{{ state.message }}</p>

                    <div class="modal-card__actions">
                        <button v-if="!isAlert && state.cancelText" class="modal__btn modal__btn--cancel"
                            @click="close(false)">
                            {{ state.cancelText }}
                        </button>
                        <button class="modal__btn" :class="[
                            state.type === 'danger' ? 'modal__btn--danger' : 'modal__btn--confirm',
                            { 'modal__btn--ok': isAlert },
                        ]" @click="close(true)">
                            {{ state.confirmText }}
                        </button>
                    </div>

                    <p class="modal-card__hint">
                        <template v-if="isAlert">Esc / Enter = chiudi</template>
                        <template v-else>Enter = conferma · Esc = annulla</template>
                    </p>
                </div>
            </div>
        </Transition>
    </Teleport>
</template>

<style scoped>
/* ── Overlay ─────────────────────────────────────────────── */
.modal-overlay {
    position: fixed;
    inset: 0;
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
}

/* ── Card ────────────────────────────────────────────────── */
.modal-card {
    width: 400px;
    max-width: 90vw;
    background: var(--bg-secondary);
    border: 1px solid var(--accent-border);
    border-radius: var(--radius-lg);
    padding: 22px 26px;
    box-shadow: 0 0 40px rgba(201, 168, 76, 0.12);
}

.modal-card__title {
    margin: 0 0 10px;
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
}

.modal-card__message {
    margin: 0 0 20px;
    font-size: 0.88rem;
    line-height: 1.5;
    color: var(--text-secondary);
}

/* ── Actions ─────────────────────────────────────────────── */
.modal-card__actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
}

.modal__btn {
    padding: 7px 18px;
    font-size: 0.82rem;
    font-weight: 500;
    border-radius: var(--radius-sm);
    border: 1px solid transparent;
    cursor: pointer;
    transition:
        background var(--transition-fast),
        color var(--transition-fast),
        border-color var(--transition-fast);
}

.modal__btn--cancel {
    background: transparent;
    color: var(--text-secondary);
    border-color: var(--border);
}

.modal__btn--cancel:hover {
    color: var(--text-primary);
    border-color: var(--border-hover);
    background: rgba(255, 255, 255, 0.04);
}

.modal__btn--confirm,
.modal__btn--ok {
    background: var(--accent-dim);
    color: var(--accent);
    border-color: var(--accent-border);
}

.modal__btn--confirm:hover,
.modal__btn--ok:hover {
    background: rgba(201, 168, 76, 0.22);
    color: var(--accent-hover);
}

.modal__btn--danger {
    background: var(--danger-hover);
    color: var(--danger);
    border-color: rgba(196, 92, 92, 0.35);
}

.modal__btn--danger:hover {
    background: rgba(196, 92, 92, 0.3);
}

/* ── Hint ────────────────────────────────────────────────── */
.modal-card__hint {
    margin: 14px 0 0;
    text-align: center;
    font-size: 0.68rem;
    color: var(--text-muted);
}

/* ── Transition ──────────────────────────────────────────── */
.modal-enter-active {
    animation: overlayIn 0.2s ease;
}

.modal-leave-active {
    animation: overlayIn 0.15s ease reverse;
}

.modal-enter-active .modal-card {
    animation: cardIn 0.25s ease;
}

.modal-leave-active .modal-card {
    animation: cardIn 0.15s ease reverse;
}

@keyframes overlayIn {
    from {
        opacity: 0;
    }

    to {
        opacity: 1;
    }
}

@keyframes cardIn {
    from {
        opacity: 0;
        transform: scale(0.95) translateY(-8px);
    }

    to {
        opacity: 1;
        transform: scale(1) translateY(0);
    }
}
</style>
