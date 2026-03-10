<script setup lang="ts">
/**
 * TasksPageView — Full-page wrapper for the tasks management view.
 */
import TasksView from '../components/tasks/TasksView.vue'
</script>

<template>
    <div class="tasks-page">
        <TasksView />
    </div>
</template>

<style scoped>
.tasks-page {
    height: 100%;
    width: 100%;
    min-width: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    align-self: stretch;
}
</style>
