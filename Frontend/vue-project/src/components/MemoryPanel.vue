<template>
  <dialog ref="dialogRef" class="memory-sheet" aria-labelledby="memory-title" @close="onClose"
    @click="onDialogClick" @cancel="onCancel">
    <div class="sheet">
      <header class="sheet-head">
        <div>
          <h2 id="memory-title" class="sheet-title" ref="titleRef" tabindex="-1">Memory</h2>
          <p class="sheet-lead">What Reacher keeps in mind for every search. Click any line to change it.</p>
        </div>
        <button type="button" class="icon-btn close-btn" @click="close" aria-label="Close memory">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
            stroke-linecap="round" aria-hidden="true">
            <line x1="6" y1="6" x2="18" y2="18" />
            <line x1="18" y1="6" x2="6" y2="18" />
          </svg>
        </button>
      </header>

      <div class="sheet-body" :aria-busy="loading">
        <p v-if="actionError" class="action-error" role="alert">{{ actionError }}</p>

        <!-- Loading -->
        <div v-if="loading" class="note" aria-hidden="true">
          <div v-for="n in 4" :key="n" class="skeleton-line" :class="{ wide: n % 2 }"></div>
        </div>

        <!-- Load error -->
        <div v-else-if="loadError" class="state">
          <p>{{ loadError }}</p>
          <button type="button" class="pill-btn" @click="load">Try again</button>
        </div>

        <!-- The note: one box, one line per fact -->
        <div v-else class="note">
          <p v-if="!visibleFacts.length" class="note-hint">
            Nothing yet. Type below, or just tell Reacher in a chat, like “Don’t show me people from Meta”.
          </p>

          <section v-for="group in groups" :key="group.kind" class="note-section"
            :aria-labelledby="`memory-group-${group.kind}`">
            <h3 :id="`memory-group-${group.kind}`" class="note-heading">{{ group.label }}</h3>

            <div v-for="fact in group.facts" :key="fact.id" class="line"
              :class="{ guess: !fact.said, pinned: fact.pinned, saving: savingId === fact.id }">
              <label class="visually-hidden" :for="`fact-${fact.id}`">{{ group.single }}</label>
              <textarea :id="`fact-${fact.id}`" :ref="(el) => setLineEl(fact.id, el)" v-model="drafts[fact.id]"
                class="line-text" rows="1" :maxlength="MAX_TEXT" spellcheck="true"
                @input="autosize($event.target)" @keydown.enter.exact.prevent="$event.target.blur()"
                @keydown.esc.stop.prevent="revert(fact, $event.target)" @blur="commit(fact)"></textarea>

              <span class="line-why" :title="whyTitle(fact)">{{ originLabel(fact) }}</span>

              <div class="line-actions">
                <button v-if="!fact.said" type="button" class="icon-btn confirm-btn"
                  :aria-label="`Confirm “${fact.text}”`" title="Confirm: make it a rule"
                  :disabled="savingId === fact.id" @click="confirmGuess(fact)">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <polyline points="5 12.5 10 17 19 7" />
                  </svg>
                </button>
                <button type="button" class="icon-btn pin-btn" :aria-pressed="!!fact.pinned"
                  :aria-label="fact.pinned ? `Unpin “${fact.text}”` : `Pin “${fact.text}” so chats can’t change it`"
                  :title="fact.pinned ? 'Unpin' : 'Pin: chats can’t change it'" :disabled="savingId === fact.id"
                  @click="togglePin(fact)">
                  <svg width="15" height="15" viewBox="0 0 24 24" :fill="fact.pinned ? 'currentColor' : 'none'"
                    stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"
                    aria-hidden="true">
                    <path d="M12 17v5" />
                    <path d="M9 3h6l-1 6 3 3v2H7v-2l3-3z" />
                  </svg>
                </button>
                <button type="button" class="icon-btn" :aria-label="`Delete “${fact.text}”`" title="Delete"
                  :disabled="savingId === fact.id" @click="scheduleDelete(fact)">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    stroke-width="2" stroke-linecap="round" aria-hidden="true">
                    <line x1="7" y1="7" x2="17" y2="17" />
                    <line x1="17" y1="7" x2="7" y2="17" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- New line for this section -->
            <div class="line add-line" :class="{ saving: addingKind === group.kind }">
              <label class="visually-hidden" :for="`add-${group.kind}`">Add to {{ group.label }}</label>
              <textarea :id="`add-${group.kind}`" v-model="newText[group.kind]" class="line-text" rows="1"
                :maxlength="MAX_TEXT" :placeholder="group.placeholder" :disabled="addingKind === group.kind"
                @input="autosize($event.target)" @keydown.enter.exact.prevent="addFact(group.kind, $event.target)"
                @keydown.esc.stop.prevent="newText[group.kind] = ''; $event.target.blur()"
                @blur="addFact(group.kind, null)"></textarea>
            </div>
          </section>
        </div>
      </div>

      <!-- Undo for a deleted line, and save status for screen readers -->
      <div class="toast-slot">
        <div v-if="pendingDelete" class="toast" role="status">
          <span>Deleted “{{ shorten(pendingDelete.fact.text) }}”</span>
          <button type="button" class="text-btn toast-btn" @click="undoDelete">Undo</button>
        </div>
        <p v-else class="visually-hidden" aria-live="polite">{{ status }}</p>
      </div>

      <footer class="sheet-foot">
        <p class="privacy">Stored encrypted. Only you and Reacher can read it. The AI model sees it only while it
          answers you.</p>
        <div v-if="visibleFacts.length" class="clear-row">
          <template v-if="confirmClear">
            <span>Delete everything Reacher remembers?</span>
            <button type="button" class="text-btn" @click="confirmClear = false">Cancel</button>
            <button type="button" class="pill-btn danger" :disabled="clearing" @click="clearAll">
              {{ clearing ? 'Clearing…' : 'Delete all' }}
            </button>
          </template>
          <button v-else type="button" class="text-btn danger-text" @click="confirmClear = true">
            Clear all memory
          </button>
        </div>
      </footer>
    </div>
  </dialog>
</template>


<script setup>
import { ref, reactive, computed, nextTick } from 'vue'

const emit = defineEmits(['closed', 'session-expired'])

const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
const REQUEST_TIMEOUT_MS = 15000
const MAX_TEXT = 120 // matches MAX_TEXT in the backend's memory.py
const UNDO_MS = 6000

// Order is the order sections appear in: exclusions first, since they change results the most.
const KINDS = [
  { kind: 'exclusion', label: 'Never show', single: 'Never show', placeholder: 'Add something to never show…' },
  { kind: 'preference', label: 'Preferences', single: 'Preference', placeholder: 'Add a preference…' },
  { kind: 'goal', label: 'Goals', single: 'Goal', placeholder: 'Add a goal…' },
  { kind: 'context', label: 'About you', single: 'About you', placeholder: 'Add something about you…' },
]

const dialogRef = ref(null)
const titleRef = ref(null)
const lineEls = new Map()

const facts = ref([])
const drafts = reactive({})   // fact id -> text being edited
const newText = reactive(Object.fromEntries(KINDS.map(k => [k.kind, ''])))
const loading = ref(false)
const loadError = ref('')
const actionError = ref('')
const status = ref('')
const savingId = ref(null)
const addingKind = ref(null)
const pendingDelete = ref(null) // { fact, timer }
const confirmClear = ref(false)
const clearing = ref(false)

// A line waiting on its Undo is hidden right away, but only deleted when the timer runs out.
const visibleFacts = computed(() =>
  facts.value.filter(f => f.id !== pendingDelete.value?.fact.id)
)

const groups = computed(() =>
  KINDS.map(k => ({ ...k, facts: visibleFacts.value.filter(f => f.kind === k.kind) }))
)

function originLabel(fact) {
  if (fact.source === 'user') return 'Written by you'
  if (fact.said) return 'You said this'
  return 'From your searches'
}

function whyTitle(fact) {
  const when = formatDate(fact.updated_at)
  if (!fact.said) {
    const hint = fact.kind === 'exclusion' ? ' It won’t hide results until you confirm it.' : ''
    return `Reacher guessed this from your recent searches.${hint} Updated ${when}.`
  }
  if (fact.source === 'user') return `You wrote or edited this. Updated ${when}.`
  return `You told Reacher this in a chat. Updated ${when}.`
}

function formatDate(iso) {
  const d = iso ? new Date(iso) : null
  if (!d || Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function shorten(text) {
  return text.length > 40 ? `${text.slice(0, 38)}…` : text
}

function clean(text) {
  return (text || '').split(/\s+/).filter(Boolean).join(' ')
}

// Grow each line to fit its text, so a long fact wraps instead of scrolling sideways.
function autosize(el) {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

function setLineEl(id, el) {
  if (el) {
    lineEls.set(id, el)
    autosize(el)
  } else {
    lineEls.delete(id)
  }
}

async function autosizeAll() {
  await nextTick()
  lineEls.forEach(autosize)
}

async function request(path, options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      credentials: 'include',
      ...options,
      signal: controller.signal,
    })
    if (res.status === 401) {
      emit('session-expired')
      close()
      throw Object.assign(new Error('unauthorized'), { quiet: true })
    }
    const body = await res.json().catch(() => ({}))
    if (!res.ok) {
      const err = new Error(`HTTP ${res.status}`)
      err.status = res.status
      err.userMessage = typeof body.detail === 'string' ? body.detail : ''
      throw err
    }
    return body
  } finally {
    clearTimeout(timer)
  }
}

function describe(err, fallback) {
  if (err.name === 'AbortError') return 'That took too long. Check your connection and try again.'
  if (err.status === 404) return 'That line was already removed. The list has been refreshed.'
  return err.userMessage || fallback
}

function setFacts(list) {
  facts.value = list
  for (const id of Object.keys(drafts)) delete drafts[id]
  for (const f of list) drafts[f.id] = f.text
  autosizeAll()
}

function replaceFact(updated) {
  facts.value = facts.value.map(f => (f.id === updated.id ? updated : f))
  drafts[updated.id] = updated.text
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await request('/memory')
    setFacts(Array.isArray(data.facts) ? data.facts : [])
  } catch (err) {
    if (err.quiet) return
    console.error('Could not load memory:', err)
    loadError.value = err.name === 'AbortError' ? 'Loading took too long.' : 'Could not load your memory.'
  } finally {
    loading.value = false
  }
}

async function patchFact(fact, body, fallback) {
  savingId.value = fact.id
  actionError.value = ''
  status.value = 'Saving…'
  try {
    const data = await request(`/memory/${encodeURIComponent(fact.id)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    replaceFact(data.fact)
    status.value = 'Saved'
    return true
  } catch (err) {
    if (err.quiet) return false
    actionError.value = describe(err, fallback)
    status.value = ''
    if (err.status === 404) load()
    return false
  } finally {
    savingId.value = null
  }
}

// Leaving a line saves it. An emptied line is deleted, with Undo.
async function commit(fact) {
  if (!facts.value.some(f => f.id === fact.id)) return
  const text = clean(drafts[fact.id])
  if (!text) {
    drafts[fact.id] = fact.text
    scheduleDelete(fact)
    return
  }
  if (text === fact.text) {
    drafts[fact.id] = fact.text   // drop stray spaces
    return
  }
  if (!(await patchFact(fact, { text }, 'Could not save that change. Try again.'))) {
    drafts[fact.id] = fact.text
  }
  autosize(lineEls.get(fact.id))
}

function revert(fact, el) {
  drafts[fact.id] = fact.text
  nextTick(() => {
    autosize(el)
    el.blur()
  })
}

function togglePin(fact) {
  return patchFact(fact, { pinned: !fact.pinned }, 'Could not change the pin. Try again.')
}

// Sending the same text marks it as the user's own: said, full confidence, safe from chat.
function confirmGuess(fact) {
  return patchFact(fact, { text: fact.text }, 'Could not confirm that. Try again.')
}

async function addFact(kind, el) {
  const text = clean(newText[kind])
  if (!text || addingKind.value) return
  const duplicate = facts.value.some(f => f.kind === kind && f.text.toLowerCase() === text.toLowerCase())
  if (duplicate) {
    actionError.value = 'That’s already in your memory.'
    return
  }
  addingKind.value = kind
  actionError.value = ''
  status.value = 'Saving…'
  try {
    const data = await request('/memory', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, text }),
    })
    facts.value = [...facts.value, data.fact]
    drafts[data.fact.id] = data.fact.text
    newText[kind] = ''
    status.value = 'Added'
  } catch (err) {
    if (err.quiet) return
    actionError.value = describe(err, 'Could not add that. Try again.')
    status.value = ''
  } finally {
    addingKind.value = null
    // Enter keeps the cursor in the new-line box, so several lines can be typed in a row.
    if (el) {
      await nextTick()
      autosize(el)
      el.focus()
    }
  }
}

function scheduleDelete(fact) {
  flushDelete()
  actionError.value = ''
  const timer = setTimeout(flushDelete, UNDO_MS)
  pendingDelete.value = { fact, timer }
  titleRef.value?.focus()
}

function undoDelete() {
  if (!pendingDelete.value) return
  const { fact, timer } = pendingDelete.value
  clearTimeout(timer)
  pendingDelete.value = null
  nextTick(() => lineEls.get(fact.id)?.focus())
}

async function flushDelete() {
  if (!pendingDelete.value) return
  const { fact, timer } = pendingDelete.value
  clearTimeout(timer)
  pendingDelete.value = null
  facts.value = facts.value.filter(f => f.id !== fact.id)
  delete drafts[fact.id]
  try {
    await request(`/memory/${encodeURIComponent(fact.id)}`, { method: 'DELETE' })
    status.value = 'Deleted'
  } catch (err) {
    if (err.quiet || err.status === 404) return
    actionError.value = describe(err, 'Could not delete that. Try again.')
    load()
  }
}

async function clearAll() {
  clearing.value = true
  actionError.value = ''
  if (pendingDelete.value) {
    clearTimeout(pendingDelete.value.timer)
    pendingDelete.value = null
  }
  try {
    await request('/memory', { method: 'DELETE' })
    setFacts([])
    confirmClear.value = false
    status.value = 'Memory cleared'
    titleRef.value?.focus()
  } catch (err) {
    if (err.quiet) return
    actionError.value = describe(err, 'Could not clear your memory. Try again.')
  } finally {
    clearing.value = false
  }
}

function open() {
  actionError.value = ''
  confirmClear.value = false
  for (const k of KINDS) newText[k.kind] = ''
  if (!dialogRef.value?.open) dialogRef.value?.showModal()
  load()
}

function close() {
  if (dialogRef.value?.open) dialogRef.value.close()
}

// Esc inside a line is handled by the line itself; here it only backs out of the clear-all confirm.
function onCancel(event) {
  if (confirmClear.value) {
    event.preventDefault()
    confirmClear.value = false
  }
}

// A click on the dialog element itself (not its content) is a click on the backdrop.
function onDialogClick(event) {
  if (event.target === dialogRef.value) close()
}

function onClose() {
  flushDelete()   // closing the sheet is the end of the Undo window
  confirmClear.value = false
  emit('closed')
}

defineExpose({ open, close })
</script>


<style scoped>
.memory-sheet {
  margin: 0 0 0 auto;
  padding: 0;
  width: min(480px, 100vw);
  max-width: 100vw;
  height: 100dvh;
  max-height: 100dvh;
  border: none;
  border-left: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-lg);
  font-family: var(--sans);
}

.memory-sheet[open] {
  animation: sheetIn 0.32s cubic-bezier(0.16, 1, 0.3, 1);
}

.memory-sheet::backdrop {
  background: color-mix(in srgb, var(--bg) 35%, rgba(10, 12, 18, 0.45));
  backdrop-filter: blur(2px);
}

@keyframes sheetIn {
  from {
    transform: translateX(24px);
    opacity: 0.4;
  }

  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.sheet {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Header */
.sheet-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 28px 24px 18px;
}

.sheet-title {
  margin: 0 0 6px;
  font-family: var(--serif);
  font-size: 1.4rem;
  font-weight: 500;
  line-height: 1.2;
  color: var(--text);
}

.sheet-title:focus {
  outline: none;
}

.sheet-lead {
  margin: 0;
  max-width: 40ch;
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.sheet-body {
  flex: 1;
  overflow-y: auto;
  padding: 0 24px 16px;
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}

.action-error {
  margin: 0 0 12px;
  padding: 10px 12px;
  border: 1px solid color-mix(in srgb, #D14343 45%, var(--border));
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, #D14343 10%, var(--surface));
  color: var(--text);
  font-size: 0.82rem;
  line-height: 1.45;
}

/* === The note === */
.note {
  padding: 6px 4px 10px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: border-color 0.15s, box-shadow 0.15s;
}

.note:focus-within {
  border-color: color-mix(in srgb, var(--green) 55%, var(--border));
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--green) 12%, transparent);
}

.note-hint {
  margin: 12px 14px 4px;
  font-size: 0.84rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.note-section + .note-section {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--border);
}

.note-heading {
  margin: 12px 14px 4px;
  font-family: var(--serif);
  font-size: 0.86rem;
  font-weight: 600;
  color: var(--text);
}

.line {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 0 10px 0 4px;
  border-radius: var(--radius-sm);
  transition: background 0.12s, opacity 0.15s;
}

.line:hover,
.line:focus-within {
  background: color-mix(in srgb, var(--surface) 70%, var(--bg));
}

.line.saving {
  opacity: 0.6;
}

.line-text {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 6px 10px;
  border: none;
  background: transparent;
  font-family: var(--sans);
  font-size: 0.92rem;
  line-height: 1.45;
  color: var(--text);
  resize: none;
  overflow: hidden;
  outline: none;
  caret-color: var(--green);
}

.line-text::selection {
  background: color-mix(in srgb, var(--green) 28%, transparent);
}

.line.guess .line-text {
  color: color-mix(in srgb, var(--text) 75%, var(--bg));
}

.add-line .line-text::placeholder {
  color: var(--text-secondary);
  opacity: 0.75;
}

.add-line .line-text:disabled {
  cursor: progress;
}

/* The reason sits at the end of the line; it is a label, not part of the text */
.line-why {
  flex-shrink: 0;
  padding-top: 8px;
  font-size: 0.72rem;
  line-height: 1.3;
  color: var(--text-secondary);
  white-space: nowrap;
  user-select: none;
  cursor: help;
}

.line.guess .line-why {
  color: var(--green);
  font-weight: 600;
}

/* Actions float over the label on hover/focus, so plain lines stay quiet */
.line-actions {
  position: absolute;
  top: 2px;
  right: 6px;
  display: flex;
  gap: 2px;
  padding-left: 12px;
  background: linear-gradient(to right, transparent, color-mix(in srgb, var(--surface) 70%, var(--bg)) 12px);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.12s;
}

.line:hover .line-actions,
.line:focus-within .line-actions {
  opacity: 1;
  pointer-events: auto;
}

/* A pinned line shows its pin even at rest */
.line.pinned::after {
  content: '';
  position: absolute;
  top: 14px;
  left: 3px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--green);
}

.line.pinned:hover::after,
.line.pinned:focus-within::after {
  opacity: 0;
}

/* Touch has no hover: keep actions in the flow, always visible */
@media (hover: none) {
  .line {
    flex-wrap: wrap;
  }

  .line-actions {
    position: static;
    opacity: 1;
    pointer-events: auto;
    background: none;
    padding-left: 0;
    margin-left: auto;
  }
}

/* States */
.state {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 32px 0;
}

.state p {
  margin: 0;
  font-size: 0.86rem;
  line-height: 1.55;
  color: var(--text-secondary);
}

.skeleton-line {
  height: 12px;
  width: 45%;
  margin: 16px 14px;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--chip-bg) 25%, var(--border) 50%, var(--chip-bg) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

.skeleton-line.wide {
  width: 75%;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Undo toast */
.toast-slot {
  padding: 0 24px;
  min-height: 0;
}

.toast {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: var(--text);
  color: var(--surface);
  font-size: 0.84rem;
  box-shadow: var(--shadow-md);
  animation: toastIn 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-btn.toast-btn {
  flex-shrink: 0;
  color: var(--surface);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.text-btn.toast-btn:focus-visible {
  outline-color: var(--surface);
}

@keyframes toastIn {
  from {
    transform: translateY(6px);
    opacity: 0;
  }

  to {
    transform: translateY(0);
    opacity: 1;
  }
}

/* Footer */
.sheet-foot {
  padding: 16px 24px 22px;
  border-top: 1px solid var(--border);
}

.privacy {
  margin: 0;
  font-size: 0.76rem;
  line-height: 1.5;
  color: var(--text-secondary);
}

.clear-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 10px;
  margin-top: 12px;
  font-size: 0.82rem;
  color: var(--text);
}

/* Buttons */
.icon-btn {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}

.icon-btn:hover:not(:disabled) {
  background: var(--chip-bg);
  color: var(--text);
}

.icon-btn[aria-pressed="true"],
.confirm-btn {
  color: var(--green);
}

.close-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  margin: -4px -6px 0 0;
}

.pill-btn {
  padding: 5px 14px;
  font-family: var(--sans);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text);
  background: var(--chip-bg);
  border: 1px solid var(--border);
  border-radius: 100px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.pill-btn:hover:not(:disabled) {
  background: var(--chip-hover);
  border-color: var(--border-hover);
}

.pill-btn.danger {
  background: #C53B3B;
  border-color: #C53B3B;
  color: #FFFFFF;
}

.pill-btn.danger:hover:not(:disabled) {
  background: #A93030;
  border-color: #A93030;
}

.text-btn {
  padding: 5px 4px;
  font-family: var(--sans);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
}

.text-btn:hover {
  color: var(--text);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.text-btn.danger-text {
  padding-left: 0;
  color: color-mix(in srgb, #D14343 85%, var(--text));
}

button:disabled {
  opacity: 0.55;
  cursor: default;
}

.icon-btn:focus-visible,
.pill-btn:focus-visible,
.text-btn:focus-visible {
  outline: 2px solid var(--green);
  outline-offset: 2px;
}

.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}

@media (pointer: coarse) {
  .icon-btn {
    width: 44px;
    height: 44px;
  }

  .pill-btn,
  .text-btn {
    min-height: 40px;
  }
}

@media (max-width: 520px) {
  .memory-sheet {
    border-left: none;
  }

  .sheet-head,
  .sheet-foot,
  .toast-slot {
    padding-left: 18px;
    padding-right: 18px;
  }

  .sheet-body {
    padding-left: 18px;
    padding-right: 18px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .memory-sheet[open],
  .toast {
    animation: none;
  }

  .skeleton-line {
    animation: none;
  }
}
</style>
