<template>
  <div class="history-backdrop" v-show="!isCollapsed" @click="isCollapsed = true"></div>
  <aside class="history-panel" :class="{ collapsed: isCollapsed }">
    <!-- Toggle button -->
    <button class="toggle-btn" @click="isCollapsed = !isCollapsed" :title="isCollapsed ? 'Expand' : 'Collapse'"
      :aria-label="isCollapsed ? 'Expand conversation history' : 'Collapse conversation history'"
      :aria-expanded="!isCollapsed">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path v-if="isCollapsed" d="M9 18l6-6-6-6" />
        <path v-else d="M15 18l-6-6 6-6" />
      </svg>
    </button>

    <div v-show="!isCollapsed" class="history-inner">
      <!-- Header -->
      <div class="history-header">
        <h2 class="history-title">Conversations</h2>
        <button class="new-chat-btn" @click="startNewChat" title="New conversation"
          aria-label="Start a new conversation">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
      </div>

      <!-- Search -->
      <div class="search-wrapper">
        <svg class="search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          v-model="searchFilter"
          type="text"
          class="search-input"
          placeholder="Search chats…"
          aria-label="Search conversations"
        />
      </div>

      <!-- Chat list -->
      <div class="chat-list" ref="chatListRef">
        <!-- Loading skeleton -->
        <template v-if="loading">
          <div v-for="n in 5" :key="n" class="chat-item skeleton">
            <div class="skeleton-title"></div>
            <div class="skeleton-meta"></div>
          </div>
        </template>

        <!-- Not logged in -->
        <div v-else-if="!userId" class="empty-state">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1.5" opacity="0.5">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
          </svg>
          <p>Log in to see your conversation history</p>
        </div>

        <!-- Fetch error -->
        <div v-else-if="loadError" class="empty-state">
          <p>{{ loadError }}</p>
          <button class="retry-btn" @click="fetchChats">Try again</button>
        </div>

        <!-- Empty state -->
        <div v-else-if="filteredChats.length === 0" class="empty-state">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-secondary)" stroke-width="1.5" opacity="0.5">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
          </svg>
          <p v-if="searchFilter">No matching conversations</p>
          <p v-else>No conversations yet</p>
        </div>

        <!-- Chat items -->
        <button
          v-else
          v-for="chat in filteredChats"
          :key="chat.session_id"
          class="chat-item"
          :class="{ active: chat.session_id === activeSessionId }"
          @click="selectChat(chat.session_id)"
        >
          <div class="chat-item-top">
            <span class="chat-title">{{ chat.title || 'Untitled' }}</span>
          </div>
          <div class="chat-meta">
            <span class="chat-date">{{ formatDate(chat.updated_at) }}</span>
            <span class="chat-count" v-if="chat.message_count">
              {{ chat.message_count }} msg{{ chat.message_count !== 1 ? 's' : '' }}
            </span>
          </div>
          <p class="chat-preview" v-if="chat.preview">{{ chat.preview }}</p>
        </button>
      </div>
    </div>
  </aside>
</template>


<script setup>
import { ref, computed, onMounted, watch } from 'vue'

const props = defineProps({
  userId: { type: String, required: true },
  activeSessionId: { type: String, default: '' },
})

const emit = defineEmits(['select-chat', 'new-chat'])

function closeOnMobile() {
  if (typeof window !== 'undefined' && window.innerWidth < 768) {
    isCollapsed.value = true
  }
}

function selectChat(sessionId) {
  emit('select-chat', sessionId)
  closeOnMobile()
}

function startNewChat() {
  emit('new-chat')
  closeOnMobile()
}

const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const REQUEST_TIMEOUT_MS = 15000

const chats = ref([])
const loading = ref(true)
const loadError = ref('')
const searchFilter = ref('')
const isCollapsed = ref(typeof window !== 'undefined' && window.innerWidth < 768)
const chatListRef = ref(null)

const filteredChats = computed(() => {
  if (!searchFilter.value.trim()) return chats.value
  const q = searchFilter.value.toLowerCase()
  return chats.value.filter(c =>
    (c.title || '').toLowerCase().includes(q) ||
    (c.preview || '').toLowerCase().includes(q)
  )
})

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffMins = Math.floor(diffMs / 60000)
  const diffHrs = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHrs < 24) return `${diffHrs}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

async function fetchChats() {
  if (!props.userId) {
    chats.value = []
    loading.value = false
    return
  }

  loading.value = true
  loadError.value = ''
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  try {
    const res = await fetch(`${API_BASE}/chats`, {
      credentials: 'include',
      signal: controller.signal
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    chats.value = Array.isArray(data.chats) ? data.chats : []
  } catch (err) {
    console.error('Failed to load chat history:', err)
    chats.value = []
    loadError.value = err.name === 'AbortError'
      ? 'Loading took too long.'
      : 'Could not load conversations.'
  } finally {
    clearTimeout(timer)
    loading.value = false
  }
}

onMounted(fetchChats)

// Re-fetch when userId changes (e.g. after login)
watch(() => props.userId, fetchChats)

function toggle() {
  isCollapsed.value = !isCollapsed.value
}

// Expose refresh so parent can call it after a new message, and toggle for the mobile nav trigger
defineExpose({ refresh: fetchChats, toggle })
</script>


<style scoped>
.history-backdrop {
  display: none;
}

.history-panel {
  width: 280px;
  height: 100%;
  border-right: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.25s ease;
  flex-shrink: 0;
}

.history-panel.collapsed {
  width: 48px;
}

.toggle-btn {
  position: absolute;
  top: 16px;
  right: -14px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  box-shadow: var(--shadow-sm);
  transition: background 0.15s, color 0.15s;
}

/* Coarse pointers (touch) need bigger hit areas than a precise mouse cursor */
@media (pointer: coarse) {
  .toggle-btn {
    width: 44px;
    height: 44px;
    right: -22px;
  }

  .new-chat-btn {
    width: 44px;
    height: 44px;
  }

  .chat-item {
    min-height: 44px;
  }
}

/* Tablet: narrower push panel, still pushes content rather than overlaying it */
@media (min-width: 768px) and (max-width: 1023px) {
  .history-panel {
    width: 240px;
  }

  .history-panel.collapsed {
    width: 48px;
  }
}

/* Phone: off-canvas drawer that overlays content instead of sharing width with it */
@media (max-width: 767px) {
  .history-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    background: rgba(26, 26, 26, 0.4);
    z-index: 150;
  }

  .history-panel,
  .history-panel.collapsed {
    position: fixed;
    top: 0;
    left: 0;
    width: min(85vw, 320px);
    height: 100dvh;
    z-index: 200;
    border-right: none;
    box-shadow: var(--shadow-lg);
    transition: transform 0.25s ease;
    transform: translateX(-100%);
  }

  .history-panel:not(.collapsed) {
    transform: translateX(0);
  }
}

.toggle-btn:hover {
  background: var(--chip-bg);
  color: var(--text);
}

.history-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* Header */
.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 16px 12px;
}

.history-title {
  font-family: var(--serif);
  font-size: 1.1rem;
  font-weight: 400;
  color: var(--text);
  margin: 0;
}

.new-chat-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
}

.new-chat-btn:hover {
  background: var(--green-light);
  border-color: var(--green);
  color: var(--green);
}

/* Search */
.search-wrapper {
  position: relative;
  padding: 0 12px 12px;
}

.search-icon {
  position: absolute;
  left: 22px;
  top: 9px;
  color: var(--text-secondary);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 8px 12px 8px 32px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  font-family: var(--sans);
  font-size: 0.8rem;
  color: var(--text);
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s;
}

.search-input::placeholder {
  color: var(--text-secondary);
  opacity: 0.6;
}

.search-input:focus {
  border-color: var(--green);
}

/* Chat list */
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 16px;
}

.chat-list::-webkit-scrollbar {
  width: 4px;
}

.chat-list::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

/* Chat item */
.chat-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 10px 12px;
  margin-bottom: 2px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  transition: background 0.12s;
  font-family: var(--sans);
}

.chat-item:hover {
  background: var(--chip-bg);
}

.chat-item.active {
  background: var(--green-light);
}

.chat-item-top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.chat-title {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.chat-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 3px;
}

.chat-date,
.chat-count {
  font-size: 0.72rem;
  color: var(--text-secondary);
}

.chat-preview {
  margin: 4px 0 0;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Active state overrides */
.chat-item.active .chat-title {
  color: var(--green);
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 40px 16px;
  text-align: center;
}

.empty-state p {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin: 0;
}

.retry-btn {
  padding: 6px 14px;
  font-size: 0.78rem;
  font-weight: 500;
  font-family: var(--sans);
  color: var(--text);
  background: var(--chip-bg);
  border: 1px solid var(--border);
  border-radius: 100px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.retry-btn:hover {
  background: var(--chip-hover);
  border-color: var(--border-hover);
}

/* Skeleton loading */
.chat-item.skeleton {
  cursor: default;
  pointer-events: none;
}

.skeleton-title,
.skeleton-meta {
  border-radius: 4px;
  background: linear-gradient(90deg, var(--chip-bg) 25%, var(--border) 50%, var(--chip-bg) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

.skeleton-title {
  height: 14px;
  width: 75%;
  margin-bottom: 6px;
}

.skeleton-meta {
  height: 10px;
  width: 45%;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>