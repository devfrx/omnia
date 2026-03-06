/**
 * useModal — Centralized modal composable for OMNIA.
 *
 * Provides a singleton reactive state and helper methods to show
 * confirm / alert / custom modals without native browser dialogs.
 * Safe for Electron — never steals renderer focus.
 */
import { reactive } from 'vue'

/** Visual type that controls button styling. */
export type ModalType = 'confirm' | 'alert' | 'danger'

/** Options accepted by {@link confirm} and {@link alert}. */
export interface ModalOptions {
  title?: string
  message: string
  type?: ModalType
  confirmText?: string
  cancelText?: string
}

/** Internal state exposed to ModalContainer. */
export interface ModalState {
  visible: boolean
  title: string
  message: string
  type: ModalType
  confirmText: string
  cancelText: string
  /** Resolves the pending promise. */
  resolve: ((value: boolean) => void) | null
  /** Element that had focus before the modal opened. */
  previousFocus: HTMLElement | null
}

const state = reactive<ModalState>({
  visible: false,
  title: '',
  message: '',
  type: 'confirm',
  confirmText: 'OK',
  cancelText: 'Annulla',
  resolve: null,
  previousFocus: null,
})

function open(opts: ModalOptions): Promise<boolean> {
  // Reject any pending modal before opening a new one
  if (state.resolve) {
    state.resolve(false)
    state.resolve = null
  }

  return new Promise<boolean>((resolve) => {
    const active = document.activeElement as HTMLElement | null
    state.previousFocus = active !== document.body ? active : null
    state.title = opts.title ?? ''
    state.message = opts.message
    state.type = opts.type ?? 'confirm'
    state.confirmText = opts.confirmText ?? 'OK'
    state.cancelText = opts.cancelText ?? 'Annulla'
    state.resolve = resolve
    state.visible = true
  })
}

/**
 * Close the modal and resolve the pending promise.
 * Focus is restored after the leave transition completes (~150ms).
 */
function close(result: boolean): void {
  const { resolve, previousFocus } = state
  state.visible = false
  state.resolve = null

  resolve?.(result)

  // Restore focus after the leave transition (~150ms) finishes
  setTimeout(() => {
    previousFocus?.focus?.()
    state.previousFocus = null
  }, 160)
}

// ── Public API ────────────────────────────────────────────────

/**
 * Show a confirmation dialog. Returns `true` if the user confirms.
 *
 * @example
 * ```ts
 * const { confirm } = useModal()
 * if (await confirm({ message: 'Sei sicuro?' })) { … }
 * ```
 */
function confirm(opts: ModalOptions): Promise<boolean> {
  return open({ type: 'confirm', confirmText: 'Conferma', ...opts })
}

/** Show an alert dialog (single OK button). Resolves when dismissed. */
async function alert(opts: Omit<ModalOptions, 'cancelText'>): Promise<void> {
  await open({ type: 'alert', confirmText: 'OK', cancelText: '', ...opts })
}

/**
 * Show a general-purpose modal with full option control.
 * Returns `true` if confirmed, `false` if cancelled.
 */
function show(opts: ModalOptions): Promise<boolean> {
  return open(opts)
}

/** Composable entry point — returns the singleton API. */
export function useModal() {
  return { state, confirm, alert, show, close } as const
}
