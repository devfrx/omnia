<script setup lang="ts">
/**
 * AmbientBackground.vue — Ambient particle and wave background.
 * Creates a living, breathing atmosphere behind the main content.
 * Pure CSS for performance (no canvas).
 */

withDefaults(defineProps<{
    state: 'idle' | 'listening' | 'thinking' | 'speaking' | 'processing'
    audioLevel: number
    subtle?: boolean
}>(), {
    subtle: false
})
</script>

<template>
    <div class="ambient" :class="[`ambient--${state}`, { 'ambient--subtle': subtle }]" aria-hidden="true">
        <!-- Gradient mesh background -->
        <div class="ambient__mesh" />

        <!-- Floating particles -->
        <div class="ambient__particles">
            <span v-for="i in 20" :key="i" class="ambient__particle" :style="{
                '--delay': `${(i * 1.7) % 8}s`,
                '--duration': `${12 + (i * 2.3) % 10}s`,
                '--x-start': `${(i * 13) % 100}%`,
                '--y-start': `${(i * 17) % 100}%`,
                '--size': `${1.5 + (i * 0.3) % 3}px`,
                '--opacity': `${0.1 + (i * 0.02) % 0.3}`,
            }" />
        </div>

        <!-- Gradient waves (bottom) -->
        <div class="ambient__waves">
            <div class="ambient__wave ambient__wave--1" />
            <div class="ambient__wave ambient__wave--2" />
            <div class="ambient__wave ambient__wave--3" />
        </div>

        <!-- Radial spotlight (follows state) -->
        <div class="ambient__spotlight" />

        <!-- Grid lines (very subtle) -->
        <div class="ambient__grid" />
    </div>
</template>

<style scoped>
.ambient {
    position: absolute;
    inset: 0;
    z-index: 0;
    overflow: hidden;
    pointer-events: none;
}

.ambient--subtle .ambient__particles,
.ambient--subtle .ambient__waves {
    opacity: 0.4;
}

/* ── Gradient Mesh ─────────────────────────────────────── */
.ambient__mesh {
    position: absolute;
    inset: 0;
    background:
        radial-gradient(ellipse at 20% 50%, rgba(201, 168, 76, 0.04) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 20%, rgba(201, 168, 76, 0.03) 0%, transparent 40%),
        radial-gradient(ellipse at 50% 80%, rgba(201, 168, 76, 0.02) 0%, transparent 50%);
    animation: meshDrift 20s ease-in-out infinite;
}

.ambient--listening .ambient__mesh {
    background:
        radial-gradient(ellipse at 20% 50%, rgba(231, 76, 60, 0.04) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 20%, rgba(201, 168, 76, 0.03) 0%, transparent 40%),
        radial-gradient(ellipse at 50% 80%, rgba(231, 76, 60, 0.02) 0%, transparent 50%);
}

.ambient--thinking .ambient__mesh {
    background:
        radial-gradient(ellipse at 20% 50%, rgba(201, 168, 76, 0.06) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 20%, rgba(201, 168, 76, 0.05) 0%, transparent 40%),
        radial-gradient(ellipse at 50% 80%, rgba(201, 168, 76, 0.04) 0%, transparent 50%);
    animation: meshDrift 10s ease-in-out infinite;
}

.ambient--speaking .ambient__mesh {
    background:
        radial-gradient(ellipse at 20% 50%, rgba(46, 204, 113, 0.04) 0%, transparent 50%),
        radial-gradient(ellipse at 80% 20%, rgba(201, 168, 76, 0.03) 0%, transparent 40%),
        radial-gradient(ellipse at 50% 80%, rgba(46, 204, 113, 0.02) 0%, transparent 50%);
}

/* ── Particles ─────────────────────────────────────────── */
.ambient__particles {
    position: absolute;
    inset: 0;
}

.ambient__particle {
    position: absolute;
    width: var(--size);
    height: var(--size);
    left: var(--x-start);
    top: var(--y-start);
    border-radius: 50%;
    background: rgba(201, 168, 76, var(--opacity));
    animation: particleFloat var(--duration) var(--delay) ease-in-out infinite;
}

.ambient--listening .ambient__particle:nth-child(odd) {
    background: rgba(231, 76, 60, var(--opacity));
}

.ambient--speaking .ambient__particle:nth-child(odd) {
    background: rgba(46, 204, 113, var(--opacity));
}

/* ── Waves ─────────────────────────────────────────────── */
.ambient__waves {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 30%;
}

.ambient__wave {
    position: absolute;
    bottom: 0;
    left: -10%;
    right: -10%;
    height: 100%;
    border-radius: 50% 50% 0 0;
    opacity: 0.5;
}

.ambient__wave--1 {
    background: linear-gradient(0deg, rgba(201, 168, 76, 0.03) 0%, transparent 100%);
    animation: wave 8s ease-in-out infinite;
}

.ambient__wave--2 {
    background: linear-gradient(0deg, rgba(201, 168, 76, 0.02) 0%, transparent 100%);
    animation: wave 12s ease-in-out infinite reverse;
    transform: translateX(5%);
}

.ambient__wave--3 {
    background: linear-gradient(0deg, rgba(201, 168, 76, 0.015) 0%, transparent 100%);
    animation: wave 15s ease-in-out infinite;
    transform: translateX(-5%);
}

/* ── Spotlight ─────────────────────────────────────────── */
.ambient__spotlight {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 60%;
    height: 60%;
    transform: translate(-50%, -50%);
    border-radius: 50%;
    background: radial-gradient(circle, rgba(201, 168, 76, 0.04) 0%, transparent 70%);
    animation: spotlightBreathing 6s ease-in-out infinite;
}

.ambient--thinking .ambient__spotlight {
    animation: spotlightBreathing 3s ease-in-out infinite;
    background: radial-gradient(circle, rgba(201, 168, 76, 0.08) 0%, transparent 70%);
}

.ambient--listening .ambient__spotlight {
    background: radial-gradient(circle, rgba(231, 76, 60, 0.05) 0%, transparent 70%);
}

/* ── Grid ──────────────────────────────────────────────── */
.ambient__grid {
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(rgba(201, 168, 76, 0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(201, 168, 76, 0.015) 1px, transparent 1px);
    background-size: 60px 60px;
    mask-image: radial-gradient(ellipse at 50% 50%, rgba(0, 0, 0, 0.5) 0%, transparent 70%);
    -webkit-mask-image: radial-gradient(ellipse at 50% 50%, rgba(0, 0, 0, 0.5) 0%, transparent 70%);
}

/* ═══════════════════════════════════════════════════════════
   Keyframes
   ═══════════════════════════════════════════════════════════ */

@keyframes meshDrift {

    0%,
    100% {
        transform: translate(0, 0) scale(1);
    }

    33% {
        transform: translate(2%, -1%) scale(1.02);
    }

    66% {
        transform: translate(-1%, 2%) scale(0.98);
    }
}

@keyframes particleFloat {

    0%,
    100% {
        transform: translate(0, 0) scale(1);
        opacity: var(--opacity);
    }

    25% {
        transform: translate(20px, -30px) scale(1.2);
        opacity: calc(var(--opacity) * 1.5);
    }

    50% {
        transform: translate(-10px, -50px) scale(0.8);
        opacity: calc(var(--opacity) * 0.6);
    }

    75% {
        transform: translate(15px, -20px) scale(1.1);
        opacity: var(--opacity);
    }
}

@keyframes wave {

    0%,
    100% {
        transform: translateY(0) scaleY(1);
    }

    50% {
        transform: translateY(-10px) scaleY(1.1);
    }
}

@keyframes spotlightBreathing {

    0%,
    100% {
        opacity: 0.8;
        transform: translate(-50%, -50%) scale(1);
    }

    50% {
        opacity: 1;
        transform: translate(-50%, -50%) scale(1.1);
    }
}
</style>
