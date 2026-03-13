<script setup lang="ts">
/**
 * OmniaSpinner.vue — Compact inline loading spinner.
 *
 * A reusable loading indicator for inline contexts: tool call execution,
 * model loading, STT/TTS initialisation, connection pending states.
 *
 * Two visual variants:
 *   "rings" — two concentric rotating arcs, mirrors the OmniaLoader aesthetic
 *             at small sizes.
 *   "dots"  — three sequentially bouncing dots, better for tight horizontal
 *             spaces (e.g. inside a button or status chip).
 *
 * Four sizes:
 *   xs → 14 px  |  sm → 20 px  |  md → 28 px  |  lg → 40 px
 */
withDefaults(
    defineProps<{
        /** Visual size of the spinner. */
        size?: 'xs' | 'sm' | 'md' | 'lg'
        /** Optional text label rendered beside the spinner. */
        label?: string
        /** Spinner style variant. */
        variant?: 'rings' | 'dots'
    }>(),
    {
        size: 'sm',
        variant: 'rings',
    }
)
</script>

<template>
    <span class="omnia-spinner" :class="[`omnia-spinner--${size}`, `omnia-spinner--${variant}`]" role="status"
        :aria-label="label || 'Caricamento in corso'">
        <!-- ── Rings variant ── -->
        <span v-if="variant === 'rings'" class="omnia-spinner__rings" aria-hidden="true">
            <!--
        Single SVG block; the viewBox is always 40×40 and the CSS
        width/height are set per-size class.  This keeps the stroke
        proportions consistent no matter which size prop is used.
      -->
            <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <!-- Outer arc: clockwise, low opacity -->
                <circle class="omnia-spinner__ring omnia-spinner__ring--outer" cx="20" cy="20" r="17"
                    stroke="var(--accent)" stroke-width="1.8" stroke-dasharray="88 18" stroke-linecap="round"
                    opacity="0.35" />
                <!-- Inner arc: counter-clockwise, higher opacity -->
                <circle class="omnia-spinner__ring omnia-spinner__ring--inner" cx="20" cy="20" r="10"
                    stroke="var(--accent)" stroke-width="1.8" stroke-dasharray="48 14" stroke-linecap="round"
                    opacity="0.70" />
            </svg>
        </span>

        <!-- ── Dots variant ── -->
        <span v-else class="omnia-spinner__dots" aria-hidden="true">
            <span class="omnia-spinner__dot omnia-spinner__dot--1" />
            <span class="omnia-spinner__dot omnia-spinner__dot--2" />
            <span class="omnia-spinner__dot omnia-spinner__dot--3" />
        </span>

        <!-- Optional text label -->
        <span v-if="label" class="omnia-spinner__label">{{ label }}</span>
    </span>
</template>

<style scoped>
/* ── Root element ────────────────────────────────────────────── */

.omnia-spinner {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 8px);
    flex-shrink: 0;
    vertical-align: middle;
}

/* ── Size scale (applied to the SVG wrapper) ─────────────────── */

.omnia-spinner__rings {
    display: flex;
    align-items: center;
    justify-content: center;
}

.omnia-spinner--xs .omnia-spinner__rings {
    width: 14px;
    height: 14px;
}

.omnia-spinner--sm .omnia-spinner__rings {
    width: 20px;
    height: 20px;
}

.omnia-spinner--md .omnia-spinner__rings {
    width: 28px;
    height: 28px;
}

.omnia-spinner--lg .omnia-spinner__rings {
    width: 40px;
    height: 40px;
}

.omnia-spinner__rings svg {
    width: 100%;
    height: 100%;
    overflow: visible;
}

/* ── Ring keyframes ──────────────────────────────────────────── */

@keyframes omniaSpin {
    to {
        transform: rotate(360deg);
    }
}

@keyframes omniaSpinRev {
    to {
        transform: rotate(-360deg);
    }
}

/* ── Ring animations ─────────────────────────────────────────── */

.omnia-spinner__ring {
    transform-origin: 20px 20px;
}

.omnia-spinner__ring--outer {
    animation: omniaSpin 2.4s linear infinite;
}

.omnia-spinner__ring--inner {
    animation: omniaSpinRev 1.6s linear infinite;
}

/* ── Dots variant ────────────────────────────────────────────── */

.omnia-spinner__dots {
    display: inline-flex;
    align-items: center;
    gap: 3px;
}

.omnia-spinner--xs .omnia-spinner__dot {
    width: 3px;
    height: 3px;
}

.omnia-spinner--sm .omnia-spinner__dot {
    width: 4px;
    height: 4px;
}

.omnia-spinner--md .omnia-spinner__dot {
    width: 5px;
    height: 5px;
}

.omnia-spinner--lg .omnia-spinner__dot {
    width: 7px;
    height: 7px;
}

.omnia-spinner__dot {
    border-radius: 50%;
    background: var(--accent);
    animation: omniaDotsJump 1.2s ease-in-out infinite;
}

.omnia-spinner__dot--1 {
    animation-delay: 0s;
    opacity: 0.5;
}

.omnia-spinner__dot--2 {
    animation-delay: 0.18s;
    opacity: 0.7;
}

.omnia-spinner__dot--3 {
    animation-delay: 0.36s;
    opacity: 0.9;
}

@keyframes omniaDotsJump {

    0%,
    80%,
    100% {
        transform: translateY(0);
        opacity: 0.4;
    }

    40% {
        transform: translateY(-4px);
        opacity: 1.0;
    }
}

/* ── Label ───────────────────────────────────────────────────── */

.omnia-spinner__label {
    font-size: var(--text-xs, 11px);
    color: var(--text-muted);
    white-space: nowrap;
}

.omnia-spinner--lg .omnia-spinner__label {
    font-size: var(--text-sm, 13px);
}
</style>
