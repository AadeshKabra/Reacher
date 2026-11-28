<template>

    <nav id="navbar" :class="{ scrolled: isScrolled }">
        <div class="nav-left">
            <button class="menu-btn" @click="historyRef?.toggle()" aria-label="Toggle conversation history">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                    stroke-linecap="round">
                    <line x1="4" y1="7" x2="20" y2="7" />
                    <line x1="4" y1="12" x2="20" y2="12" />
                    <line x1="4" y1="17" x2="20" y2="17" />
                </svg>
            </button>
            <a href="/" class="logo">Reacher</a>
        </div>
        <h1 class="visually-hidden">Reacher — find people and companies to reach out to</h1>
        <div class="nav-right">
            <button class="theme-toggle" @click="toggleTheme"
                :aria-label="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'">
                <svg v-if="theme === 'dark'" width="18" height="18" viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="4" />
                    <line x1="12" y1="2" x2="12" y2="4" />
                    <line x1="12" y1="20" x2="12" y2="22" />
                    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                    <line x1="2" y1="12" x2="4" y2="12" />
                    <line x1="20" y1="12" x2="22" y2="12" />
                    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
                </svg>
                <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
            </button>
            <button v-if="!userName" class="profile-btn" @click="login">
                <span class="profile-name">Login</span>
            </button>
            <div v-else class="profile-menu" ref="profileMenuRef" @keydown.esc="closeProfileMenu(true)">
                <button class="profile-btn" ref="profileBtnRef" @click="isProfileMenuOpen = !isProfileMenuOpen"
                    aria-haspopup="menu" :aria-expanded="isProfileMenuOpen" aria-controls="profile-dropdown">
                    <span class="profile-name">{{ userName }}</span>
                    <svg class="profile-caret" :class="{ open: isProfileMenuOpen }" width="14" height="14"
                        viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <polyline points="6 9 12 15 18 9" />
                    </svg>
                </button>
                <div v-if="isProfileMenuOpen" id="profile-dropdown" class="profile-dropdown" role="menu">
                    <div class="profile-dropdown-header">Signed in as<br><strong>{{ userName }}</strong></div>
                    <button class="profile-dropdown-item" role="menuitem" @click="openMemory">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M12 3a6 6 0 0 0-6 6c0 2.2 1.2 3.6 2.2 4.6.8.8 1.3 1.6 1.3 2.6V17h5v-.8c0-1 .5-1.8 1.3-2.6 1-1 2.2-2.4 2.2-4.6a6 6 0 0 0-6-6z" />
                            <line x1="9.5" y1="20" x2="14.5" y2="20" />
                        </svg>
                        Your memory
                    </button>
                    <button class="profile-dropdown-item" role="menuitem" @click="logout" :disabled="isLoggingOut">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                            <polyline points="16 17 21 12 16 7" />
                            <line x1="21" y1="12" x2="9" y2="12" />
                        </svg>
                        {{ isLoggingOut ? 'Logging out…' : 'Log out' }}
                    </button>
                </div>
            </div>
        </div>
    </nav>

    <div class="app-layout">
        <ChatHistory ref="historyRef" :userId="userId" :activeSessionId="currentSessionId" @select-chat="loadChat"
            @new-chat="startNewChat" @session-expired="clearUser" />
        <MemoryPanel ref="memoryRef" @closed="onMemoryClosed" @session-expired="clearUser" />

        <main ref="mainRef">
            <div class="main-inner">

            <!-- Hero -->
            <section class="hero-section fade-in fade-in-1" v-if="!querySubmitted">
                <p class="hero-title">Find people. <em>Reach Out.</em></p>
                <p class="hero-sub">Upload your resume to get started. Reacher uses your profile to find the right
                    people
                    and craft emails that get replies.</p>
            </section>

            <!-- Upload Section -->
            <section class="fade-in fade-in-2" v-if="!querySubmitted">
                <div class="section-label">01 — Your Profile</div>
                <div class="upload-zone" id="dropzone" :class="{ 'signed-out': !userId }" role="button" tabindex="0"
                    :aria-busy="isUploading"
                    :aria-label="!userId ? 'Sign in with Google to upload your resume.' : (fileName ? `Resume uploaded: ${fileName}. Press Enter to replace it.` : 'Upload your resume. PDF, DOC, or DOCX, up to 5 megabytes.')"
                    @click="userId ? uploadResume() : login()"
                    @keydown.enter.prevent="userId ? uploadResume() : login()"
                    @keydown.space.prevent="userId ? uploadResume() : login()" @dragover.prevent @dragenter.prevent
                    @drop.prevent="userId ? handleDrop($event) : login()"
                    :style="resumeFile ? 'cursor: default; border-style: solid; border-color: var(--green); background: var(--green-light)' : ''">
                    <div class="upload-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round"
                            stroke-linejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                            <line x1="12" y1="18" x2="12" y2="12" />
                            <polyline points="9 15 12 12 15 15" />
                        </svg>
                    </div>
                    <p class="upload-text" v-if="!userId">Sign in to upload your resume</p>
                    <p class="upload-text" v-else-if="isUploading">Uploading…</p>
                    <p class="upload-text" v-else-if="!fileName">Drop your resume here or <span>browse</span></p>
                    <p class="upload-text upload-text-filename" v-else style="color: var(--green)" :title="fileName">
                        {{ fileName }}</p>
                    <p class="upload-sub" v-if="!userId">Used to personalize your results — <span
                            class="upload-link">sign in with Google</span></p>
                    <p class="upload-sub" v-else-if="uploadError" role="alert" style="color: #B3261E">{{ uploadError
                        }}
                    </p>
                    <p class="upload-sub" v-else-if="isUploading">This may take a moment</p>
                    <p class="upload-sub" v-else-if="!fileName">Optional — PDF, DOC, or DOCX, up to 5MB. You can
                        search without it.</p>
                    <p class="upload-sub" v-else>
                        Resume uploaded
                        <span style="color: var(--green); cursor: pointer; text-decoration: underline;"
                            @click.stop="clearFile" @keydown.enter.stop.prevent="clearFile"
                            @keydown.space.stop.prevent="clearFile" role="button" tabindex="0">Remove</span>
                    </p>

                    <input type="file" ref="fileInput" @change="handleFile" accept=".pdf,.doc,.docx"
                        aria-hidden="true" tabindex="-1" style="display: none">
                </div>
            </section>

            <!-- Chat Section -->
            <section class="chat" v-if="querySubmitted" ref="chatSectionRef">
                <div class="chat-messages">
                    <div v-for="(msg, i) in messages" :key="i" class="message"
                        :class="[msg.role, { 'has-leads': msg.leads && msg.leads.length, loading: msg.loading, error: msg.error, notice: msg.notice }]">

                        <!-- User message: always plain text -->
                        <p v-if="msg.role === 'user'" v-html="renderMarkdown(msg.text)"></p>

                        <!-- Loading status while waiting for the backend -->
                        <template v-else-if="msg.loading">
                            <div class="loader-head">
                                <svg class="loader-ring" viewBox="0 0 24 24" aria-hidden="true">
                                    <circle class="loader-ring-track" cx="12" cy="12" r="9" />
                                    <circle class="loader-ring-arc" cx="12" cy="12" r="9" />
                                </svg>
                                <p class="loader-label" role="status" aria-live="polite">
                                    {{ msg.steps[loadingStepIndex(elapsedSeconds)] }}<span class="loading-dots"
                                        aria-hidden="true"></span>
                                </p>
                            </div>

                            <div class="loader-bar" role="progressbar" aria-label="Estimated progress"
                                aria-valuemin="0" aria-valuemax="100"
                                :aria-valuenow="loadingProgress(elapsedSeconds)">
                                <div class="loader-bar-fill"
                                    :style="{ width: loadingProgress(elapsedSeconds) + '%' }"></div>
                            </div>

                            <ol class="loader-steps">
                                <li v-for="(step, k) in msg.steps" :key="k" :class="{
                                    done: k < loadingStepIndex(elapsedSeconds),
                                    active: k === loadingStepIndex(elapsedSeconds)
                                }">
                                    <span class="loader-step-dot" aria-hidden="true">
                                        <svg v-if="k < loadingStepIndex(elapsedSeconds)" viewBox="0 0 24 24">
                                            <polyline points="5 12.5 10 17 19 7" />
                                        </svg>
                                    </span>
                                    {{ step }}
                                </li>
                            </ol>

                            <p class="loading-meta">
                                <template v-if="elapsedSeconds < SLOW_QUERY_SECONDS">Hang tight, good matches take a moment</template>
                                <template v-else>Still working. This one's taking longer than usual</template>
                            </p>
                        </template>

                        <!-- Assistant with leads: show cards -->
                        <template v-else-if="msg.leads && msg.leads.length">
                            <p v-if="msg.personalized" class="personalized-badge">Personalized using your résumé</p>
                            <p v-if="msg.text" class="leads-summary">{{ msg.text }}</p>
                            <div class="leads-grid" :class="{ 'has-open': gridHasOpenCard(i) }">
                                <article v-for="(lead, j) in msg.leads" :key="j" class="lead-card"
                                    :class="{ open: expandedLead === leadKey(i, j) }">
                                    <header class="lead-head">
                                        <div class="lead-avatar" :class="{ 'has-logo': logoShown(lead) }"
                                            aria-hidden="true">
                                            <img v-if="logoUrl(lead) && !logoFailed.has(lead.domain)"
                                                v-show="logoShown(lead)" :src="logoUrl(lead)" alt="" width="28"
                                                height="28" loading="lazy" referrerpolicy="no-referrer"
                                                @load="onLogoLoad(lead.domain, $event)"
                                                @error="markLogoFailed(lead.domain)" />
                                            <template v-if="!logoShown(lead)">{{ leadInitials(lead.name) }}</template>
                                        </div>
                                        <div class="lead-id">
                                            <h3 class="lead-name" :title="lead.name || 'Unnamed contact'">{{ lead.name
                                                || 'Unnamed contact' }}</h3>
                                            <p class="lead-title" v-if="lead.title"
                                                :title="lead.title">{{ lead.title }}</p>
                                            <p class="lead-company" v-if="lead.company"
                                                :title="lead.company">{{ lead.company }}</p>
                                        </div>
                                    </header>
                                    <div class="lead-why" v-if="lead.relevance">
                                        <p class="lead-relevance" :id="'lead-rel-' + leadKey(i, j)"
                                            :class="{ clamped: expandedLead !== leadKey(i, j) }"
                                            :ref="(el) => setRelevanceEl(leadKey(i, j), el)">{{ lead.relevance }}</p>
                                        <button v-if="clampableLeads.has(leadKey(i, j))" type="button"
                                            class="lead-more" :aria-expanded="expandedLead === leadKey(i, j)"
                                            :aria-controls="'lead-rel-' + leadKey(i, j)"
                                            @click="toggleLead(leadKey(i, j))">
                                            {{ expandedLead === leadKey(i, j) ? 'Show less' : 'Show more' }}
                                        </button>
                                    </div>
                                    <footer class="lead-actions">
                                        <template v-if="lead.email">
                                            <a :href="'mailto:' + lead.email" class="lead-btn email-btn"
                                                :title="lead.email">
                                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
                                                    stroke="currentColor" stroke-width="2" stroke-linecap="round"
                                                    stroke-linejoin="round" aria-hidden="true">
                                                    <rect x="3" y="5" width="18" height="14" rx="2" />
                                                    <polyline points="3 7 12 13 21 7" />
                                                </svg>
                                                Email
                                            </a>
                                            <span class="lead-email-addr" :title="lead.email">{{ lead.email }}</span>
                                        </template>
                                        <a v-if="lead.source_url" :href="lead.source_url" target="_blank"
                                            rel="noopener noreferrer" class="lead-btn source-btn">
                                            Source
                                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                                                stroke="currentColor" stroke-width="2.2" stroke-linecap="round"
                                                stroke-linejoin="round" aria-hidden="true">
                                                <line x1="7" y1="17" x2="17" y2="7" />
                                                <polyline points="8 7 17 7 17 16" />
                                            </svg>
                                        </a>
                                    </footer>
                                </article>
                            </div>
                        </template>

                        <!-- Assistant without leads: plain text -->
                        <p v-else v-html="renderMarkdown(msg.text)"></p>

                    </div>
                </div>
            </section>

            <!-- Search Section -->
            <section :class="['search-section', 'fade-in', 'fade-in-3', { 'search-fixed': querySubmitted, 'section-gap': !querySubmitted }]">
                <div class="section-label" v-if="!querySubmitted">02 — What are you looking for?</div>
                <!-- Attachment status: shown once a file is picked from the pin, or if that upload fails -->
                <div v-if="querySubmitted && (isUploading || uploadError || fileName)" class="attach-status"
                    :class="{ error: uploadError, uploading: isUploading }" role="status" aria-live="polite">
                    <svg v-if="isUploading" class="attach-spinner" viewBox="0 0 24 24" aria-hidden="true">
                        <circle cx="12" cy="12" r="9" />
                    </svg>
                    <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                        stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path v-if="uploadError" d="M12 8v5M12 16h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
                        <template v-else>
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                        </template>
                    </svg>
                    <span class="attach-name" v-if="!uploadError" :title="fileName">{{ fileName }}</span>
                    <span class="attach-note">{{ uploadError || (isUploading ? 'Reading your document…'
                        : 'Used for your next searches') }}</span>
                    <button v-if="uploadError" class="attach-dismiss" @click="uploadError = ''"
                        aria-label="Dismiss upload error">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                            stroke-width="2.4" stroke-linecap="round" aria-hidden="true">
                            <line x1="6" y1="6" x2="18" y2="18" />
                            <line x1="18" y1="6" x2="6" y2="18" />
                        </svg>
                    </button>
                </div>

                <div class="search-wrapper">
                    <div class="search-field">
                        <input class="search-input" type="text" placeholder="Find somebody to reach out to..."
                            v-model="searchQuery" id="search-input" @keydown.enter="getQueryResponse"
                            :disabled="isLoading">
                        <button class="attach-btn" type="button" @click="userId ? chatFileInput?.click() : login()"
                            :disabled="isUploading"
                            :aria-label="!userId ? 'Sign in to attach your resume' : 'Attach your resume or a document (PDF, DOC, or DOCX)'"
                            :title="!userId ? 'Sign in to attach your resume' : 'Attach resume or document'">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                                stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                <path
                                    d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                            </svg>
                        </button>
                        <input type="file" ref="chatFileInput" @change="handleFile" accept=".pdf,.doc,.docx"
                            aria-hidden="true" tabindex="-1" style="display: none">
                    </div>
                    <button class="search-btn" @click="getQueryResponse" :disabled="isLoading" aria-label="Search">
                        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round"
                            stroke-linejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13" />
                            <polygon points="22 2 15 22 11 13 2 9 22 2" />
                        </svg>
                    </button>
                </div>

                <div class="chips" id="chips" v-if="!querySubmitted">
                    <span class="chip" role="button" tabindex="0" @click="fillSearch('Find ML engineers at Nvidia')"
                        @keydown.enter.prevent="fillSearch('Find ML engineers at Nvidia')"
                        @keydown.space.prevent="fillSearch('Find ML engineers at Nvidia')">Find ML engineers at
                        Nvidia</span>
                    <span class="chip" role="button" tabindex="0"
                        @click="fillSearch('Cybersecurity startups hiring in DC')"
                        @keydown.enter.prevent="fillSearch('Cybersecurity startups hiring in DC')"
                        @keydown.space.prevent="fillSearch('Cybersecurity startups hiring in DC')">Cybersecurity
                        startups
                        hiring in DC</span>
                    <span class="chip" role="button" tabindex="0"
                        @click="fillSearch('Who leads backend eng at Stripe?')"
                        @keydown.enter.prevent="fillSearch('Who leads backend eng at Stripe?')"
                        @keydown.space.prevent="fillSearch('Who leads backend eng at Stripe?')">Who leads backend eng
                        at
                        Stripe?</span>

                </div>
            </section>

            </div>
        </main>

    </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onBeforeUnmount, watch } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { v4 as uuidv4 } from 'uuid';
import ChatHistory from './ChatHistory.vue'
import MemoryPanel from './MemoryPanel.vue'

const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 30000;
const MAX_RESUME_SIZE = 5 * 1024 * 1024; // 5MB, matches MAX_RESUME_BYTES in the backend
const UPLOAD_TIMEOUT_MS = 120000;
// A query runs several LLM calls (classifier, planner, answer), each a fresh Claude Code process
const QUERY_TIMEOUT_MS = 180000;
const ALLOWED_RESUME_TYPES = ['.pdf', '.doc', '.docx'];

function renderMarkdown(text) {
    return DOMPurify.sanitize(marked.parse(text ?? '', { breaks: true }));
}

// Some answers (mostly older saved ones) carry their leads as JSON inside the text, sometimes
// wrapped in a ``` fence. Unpack them so both live and reloaded answers render as cards.
function extractLeads(rawText, rawLeads) {
    let leads = Array.isArray(rawLeads) ? rawLeads : [];
    let text = typeof rawText === 'string' ? rawText : '';

    if (!leads.length && text) {
        let cleaned = text.trim();
        if (cleaned.startsWith('```')) cleaned = cleaned.split('\n').slice(1).join('\n');
        if (cleaned.endsWith('```')) cleaned = cleaned.slice(0, cleaned.lastIndexOf('```'));
        cleaned = cleaned.trim();
        try {
            const parsed = JSON.parse(cleaned);
            if (parsed && Array.isArray(parsed.leads)) {
                leads = parsed.leads;
                text = parsed.summary || parsed.suggestions || '';
            }
        } catch (err) {
            // not JSON — show the text as-is
        }
    }
    return { text, leads };
}

function leadInitials(name) {
    const parts = (name || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '?';
    return (parts[0][0] + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase();
}

// --- Company logos ---
// The browser loads the favicon straight from Google's favicon service; nothing is stored.
// Google answers an unknown domain with a tiny 16px globe, so anything under 32px counts as no logo.
const DOMAIN_RE = /^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$/;
const logoLoaded = ref(new Set());
const logoFailed = ref(new Set());

function logoUrl(lead) {
    const d = typeof lead?.domain === 'string' ? lead.domain.trim().toLowerCase() : '';
    if (!DOMAIN_RE.test(d)) return '';
    return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(d)}&sz=128`;
}

function logoShown(lead) {
    return !!logoUrl(lead) && logoLoaded.value.has(lead.domain) && !logoFailed.value.has(lead.domain);
}

function onLogoLoad(domain, event) {
    if (event.target.naturalWidth < 32) {
        markLogoFailed(domain);
        return;
    }
    logoLoaded.value = new Set(logoLoaded.value).add(domain);
}

function markLogoFailed(domain) {
    logoFailed.value = new Set(logoFailed.value).add(domain);
}

function hasAllowedExtension(filename) {
    const lower = (filename || '').toLowerCase();
    return ALLOWED_RESUME_TYPES.some((ext) => lower.endsWith(ext));
}

function fetchWithTimeout(url, options = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return fetch(url, { credentials: 'include', ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
}

const SIGN_IN_PROMPT = 'Sign in with Google to search. Use the Login button at the top right.';
const THEME_STORAGE_KEY = 'reacher-theme';

const theme = ref('light');

function applyTheme(value) {
    theme.value = value;
    document.documentElement.setAttribute('data-theme', value);
}

function toggleTheme() {
    const next = theme.value === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    localStorage.setItem(THEME_STORAGE_KEY, next);
}

const searchQuery = ref('')
const isScrolled = ref(false)
const userName = ref('')

const fileInput = ref(null);
const chatFileInput = ref(null); // the pin in the search bar; the drop zone's input isn't mounted during a chat
const mainRef = ref(null);

async function scrollChatToBottom() {
    await nextTick();
    mainRef.value?.scrollTo({ top: mainRef.value.scrollHeight, behavior: 'smooth' });
}
const fileName = ref('')
const resumeFile = ref(null);
const uploadError = ref('');
const isUploading = ref(false);
const hasResume = ref(false);
let personalizedNoticeShown = false;
const querySubmitted = ref(false);
const messages = ref([]);

// --- Lead card "Show more" ---
// Card key is "<message index>-<lead index>". Only one card is open at a time.
const expandedLead = ref(null);
// Keys of cards whose text is longer than the 3-line clamp, so they need a button.
const clampableLeads = ref(new Set());
const relevanceEls = new Map();

function leadKey(i, j) {
    return `${i}-${j}`;
}

function setRelevanceEl(key, el) {
    if (el) relevanceEls.set(key, el);
    else relevanceEls.delete(key);
}

function measureClamps() {
    const next = new Set();
    for (const [key, el] of relevanceEls) {
        if (key === expandedLead.value) {
            // An open card isn't clamped, so it can't be measured; it had a button to get here.
            next.add(key);
        } else if (el.scrollHeight > el.clientHeight + 1) {
            next.add(key);
        }
    }
    clampableLeads.value = next;
}

function toggleLead(key) {
    expandedLead.value = expandedLead.value === key ? null : key;
}

function gridHasOpenCard(i) {
    return typeof expandedLead.value === 'string' && expandedLead.value.startsWith(`${i}-`);
}

let clampFrame = 0;
function scheduleMeasureClamps() {
    cancelAnimationFrame(clampFrame);
    clampFrame = requestAnimationFrame(measureClamps);
}

// A new array means a new reply or another chat: close any open card, then re-measure.
watch(messages, () => {
    expandedLead.value = null;
    scheduleMeasureClamps();
}, { flush: 'post' });
watch(() => messages.value.length, scheduleMeasureClamps, { flush: 'post' });

const userId = ref('')

const currentSessionId = ref(uuidv4());

const historyRef = ref(null);
const chatSectionRef = ref(null);
const isLoading = ref(false);
const elapsedSeconds = ref(0);
let elapsedTimer = null;

function statusForQuery(query) {
    const q = query.toLowerCase();
    if (/\b(startup|startups|compan(?:y|ies)|organizations?|hiring)\b/.test(q)) {
        return ['Finding companies', 'Scanning the web', 'Ranking matches'];
    }
    if (/\b(who|engineer|engineers|people|person|lead|leads|manager|hire|recruit)\b/.test(q)) {
        return ['Finding leads', 'Searching the web', 'Personalizing matches'];
    }
    return ['Reading your question', 'Thinking', 'Putting it together'];
}

// The backend doesn't report progress, so the loader estimates it from elapsed time.
// Steps only ever move forward, and the bar eases toward 95% so it never claims to be done.
const LOADING_STEP_STARTS = [0, 8, 30]; // seconds at which each step becomes active
const SLOW_QUERY_SECONDS = 90;

function loadingStepIndex(elapsed) {
    let index = 0;
    LOADING_STEP_STARTS.forEach((start, i) => { if (elapsed >= start) index = i; });
    return index;
}

function loadingProgress(elapsed) {
    return Math.min(95, Math.round(4 + 96 * (1 - Math.exp(-elapsed / 40))));
}

function clearLoadingStatusTimer() {
    if (elapsedTimer) {
        clearInterval(elapsedTimer);
        elapsedTimer = null;
    }
}

function removeLoadingMessages() {
    clearLoadingStatusTimer();
    messages.value = messages.value.filter((msg) => !msg.loading);
}


onMounted(() => {
    window.addEventListener('scroll', () => {
        isScrolled.value = window.scrollY > 10
    })

    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    applyTheme(storedTheme || (prefersDark ? 'dark' : 'light'));

    document.addEventListener('click', handleOutsideClick);
    // Card width changes with the window, and so does whether the text fits in 3 lines.
    window.addEventListener('resize', scheduleMeasureClamps);

    localStorage.removeItem('userName');
    localStorage.removeItem('userId');
    loadCurrentUser();
})

async function loadCurrentUser() {
    try {
        const res = await fetchWithTimeout(`${API_BASE}/me`);
        if (!res.ok) {
            clearUser();
            return;
        }
        const user = await res.json();
        userId.value = user.email || '';
        userName.value = user.name || '';
    } catch (err) {
        console.error('Could not check sign-in status:', err);
        clearUser();
    }
}

function clearUser() {
    userId.value = '';
    userName.value = '';
}

function fillSearch(text) {
    searchQuery.value = text
}

function login() {
    window.location.href = `${API_BASE}/auth/google`;
}

const isProfileMenuOpen = ref(false);
const isLoggingOut = ref(false);
const profileMenuRef = ref(null);
const profileBtnRef = ref(null);

function closeProfileMenu(returnFocus = false) {
    if (!isProfileMenuOpen.value) return;
    isProfileMenuOpen.value = false;
    if (returnFocus) profileBtnRef.value?.focus();
}

const memoryRef = ref(null);

function openMemory() {
    isProfileMenuOpen.value = false;
    memoryRef.value?.open();
}

// The menu item that opened the sheet is gone by now, so send focus back to the profile button.
function onMemoryClosed() {
    profileBtnRef.value?.focus();
}

function handleOutsideClick(event) {
    if (profileMenuRef.value && !profileMenuRef.value.contains(event.target)) {
        closeProfileMenu();
    }
}

async function logout() {
    if (isLoggingOut.value) return;
    isLoggingOut.value = true;
    try {
        await fetchWithTimeout(`${API_BASE}/logout`, { method: 'POST' });
    } catch (err) {
        // The cookie may still be set; the next /me check will show the real state
        console.error('Logout request failed:', err);
    } finally {
        isLoggingOut.value = false;
        isProfileMenuOpen.value = false;
        clearUser();
        clearFile();
        startNewChat();
    }
}

function uploadResume() {
    if (isUploading.value) return;
    fileInput.value.click();
}

function startNewChat() {
    clearLoadingStatusTimer();
    currentSessionId.value = uuidv4();
    messages.value = [];
    querySubmitted.value = false;
    isLoading.value = false;
    personalizedNoticeShown = false;
}

onBeforeUnmount(() => {
    clearLoadingStatusTimer();
    document.removeEventListener('click', handleOutsideClick);
    window.removeEventListener('resize', scheduleMeasureClamps);
    cancelAnimationFrame(clampFrame);
});

async function uploadResumeBackend() {
    if (!resumeFile.value) {
        return;
    }
    if (!userId.value) {
        clearFile();
        uploadError.value = 'Sign in with Google to upload your resume.';
        return;
    }

    isUploading.value = true;
    uploadError.value = '';
    const uploadedName = fileName.value;

    const formData = new FormData();
    formData.append('file', resumeFile.value);

    try {
        // Extracting the profile runs an LLM call on the server, so allow longer than a normal request
        const res = await fetchWithTimeout(`${API_BASE}/uploadResume`, {
            method: 'POST',
            body: formData
        }, UPLOAD_TIMEOUT_MS);

        if (res.status === 401) {
            clearUser();
            throw new Error('unauthorized');
        }
        if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            const serverError = new Error(`Server returned ${res.status}`);
            serverError.userMessage = typeof body.error === 'string' ? body.error : '';
            throw serverError;
        }
        await res.json();
        hasResume.value = true;
        if (querySubmitted.value) {
            messages.value.push({
                role: 'assistant',
                text: `Got it. I'll use ${uploadedName} to personalize your next searches.`,
                leads: [],
                notice: true
            });
            scrollChatToBottom();
        }
    } catch (err) {
        console.error('Resume upload failed:', err);
        uploadError.value = err.name === 'AbortError'
            ? 'Upload timed out. Please try again.'
            : err.message === 'unauthorized'
                ? 'Your sign-in expired. Sign in with Google again to upload your resume.'
                : (err.userMessage || 'Upload failed. Please try again.');
        resumeFile.value = null;
        fileName.value = '';
    } finally {
        // Reset both pickers so choosing the same file again still fires a change event
        if (fileInput.value) fileInput.value.value = '';
        if (chatFileInput.value) chatFileInput.value.value = '';
        isUploading.value = false;
    }
}

function validateResumeFile(file) {
    if (!hasAllowedExtension(file.name)) {
        uploadError.value = 'Unsupported file type. Please upload a PDF, DOC, or DOCX.';
        return false;
    }
    if (file.size > MAX_RESUME_SIZE) {
        uploadError.value = 'File is too large. Maximum size is 5MB.';
        return false;
    }
    return true;
}

function handleFile(event) {
    const file = event.target.files[0];
    if (!file || isUploading.value) return;

    uploadError.value = '';
    if (!validateResumeFile(file)) {
        event.target.value = '';
        return;
    }

    resumeFile.value = file;
    fileName.value = file.name;
    uploadResumeBackend();
}

function handleDrop(event) {
    if (isUploading.value) return;
    const file = event.dataTransfer.files[0];
    if (!file) return;

    uploadError.value = '';
    if (!validateResumeFile(file)) return;

    resumeFile.value = file;
    fileName.value = file.name;
    uploadResumeBackend();
}

async function getQueryResponse() {
    const query = searchQuery.value.trim();
    if (!query || isLoading.value) return;

    if (!userId.value) {
        querySubmitted.value = true;
        messages.value.push({ role: "assistant", text: SIGN_IN_PROMPT, leads: [], notice: true });
        return;
    }

    isLoading.value = true;
    querySubmitted.value = true;
    searchQuery.value = '';
    messages.value.push({ role: "user", text: query });

    messages.value.push({ role: "assistant", text: '', steps: statusForQuery(query), loading: true });
    elapsedSeconds.value = 0;
    elapsedTimer = setInterval(() => {
        elapsedSeconds.value += 1;
    }, 1000);

    await nextTick();
    chatSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
        const response = await fetchWithTimeout(`${API_BASE}/processQuery`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId.value,
                message: query
            })
        }, QUERY_TIMEOUT_MS);

        if (response.status === 401) {
            clearUser();
            removeLoadingMessages();
            messages.value.push({ role: "assistant", text: SIGN_IN_PROMPT, leads: [], notice: true });
            return;
        }
        if (!response.ok) {
            const body = await response.json().catch(() => ({}));
            const serverError = new Error(`Server returned ${response.status}`);
            serverError.userMessage = typeof body.error === 'string' ? body.error : '';
            throw serverError;
        }

        const data = await response.json();
        const { text, leads } = extractLeads(data.response || data.suggestions || "", data.leads);

        const personalized = hasResume.value && leads.length > 0 && !personalizedNoticeShown;
        if (personalized) personalizedNoticeShown = true;

        removeLoadingMessages();
        messages.value.push({ role: "assistant", text, leads, personalized });
        historyRef.value?.refresh();
    } catch (err) {
        console.error(err);
        removeLoadingMessages();
        messages.value.push({
            role: "assistant",
            text: err.name === 'AbortError'
                ? "The search is taking longer than expected. Please try again."
                : (err.userMessage || "Something went wrong while searching. Please try again."),
            leads: [],
            error: true
        });
    } finally {
        isLoading.value = false;
    }
}

function clearFile() {
    resumeFile.value = null;
    fileName.value = '';
    uploadError.value = '';
    hasResume.value = false;
    if (fileInput.value) fileInput.value.value = '';
}

async function loadChat(sessionId) {
    clearLoadingStatusTimer();
    isLoading.value = false;
    currentSessionId.value = sessionId;
    querySubmitted.value = true;
    messages.value = []

    try {
        const res = await fetchWithTimeout(`${API_BASE}/chat/${encodeURIComponent(sessionId)}`);
        if (res.status === 401) clearUser();
        if (!res.ok) throw new Error(`Server returned ${res.status}`);

        const data = await res.json();
        messages.value = (data.messages || []).map(m => {
            if (m.role !== 'assistant') return { role: m.role, text: m.content, leads: [] };
            const { text, leads } = extractLeads(m.content, m.leads);
            return { role: m.role, text, leads };
        })
    } catch (err) {
        console.error('Error loading chat:', err);
        messages.value = [{
            role: 'assistant',
            text: 'Could not load this conversation. Please try again.',
            leads: [],
            error: true
        }];
    }
}

</script>

<style>
:root {
    --bg: #F4F5F7;
    --surface: #FFFFFF;
    --text: #2E1F3D;
    --text-secondary: #686C76;
    --accent: #3D2B54;
    --border: #E1E3E8;
    --border-hover: #C9CDD6;
    --chip-bg: #EBEDF1;
    --chip-hover: #E0E3E9;
    --upload-bg: #EFF1F4;
    --upload-border: #D6DAE1;
    --green: #3E82A8;
    --green-light: #DCEDF5;
    --user-bubble: #E3E7EE;
    --user-bubble-border: #D3D8E1;
    --serif: 'Sora', -apple-system, sans-serif;
    --sans: 'Sora', -apple-system, sans-serif;
    --shadow-sm: 0 1px 2px rgba(30, 35, 45, 0.06), 0 1px 3px rgba(30, 35, 45, 0.04);
    --shadow-md: 0 4px 12px rgba(30, 35, 45, 0.09), 0 1px 4px rgba(30, 35, 45, 0.05);
    --shadow-lg: 0 14px 36px rgba(30, 35, 45, 0.12), 0 4px 12px rgba(30, 35, 45, 0.06);
    --radius: 17px;
    --radius-sm: 12.5px;
}

:root[data-theme="dark"] {
    --bg: #0B0E14;
    --surface: #121722;
    --text: #E6E9F0;
    --text-secondary: #8A93A6;
    --accent: #1F2937;
    --border: #232A38;
    --border-hover: #37414F;
    --chip-bg: #1A2130;
    --chip-hover: #232C3D;
    --upload-bg: #141A26;
    --upload-border: #2B3447;
    --green: #22D3C7;
    --green-light: #123838;
    --user-bubble: #34425E;
    --user-bubble-border: #46567A;
    --serif: 'Sora', -apple-system, sans-serif;
    --sans: 'Sora', -apple-system, sans-serif;
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.4);
    --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4), 0 1px 4px rgba(0, 0, 0, 0.3);
    --shadow-lg: 0 12px 32px rgba(0, 0, 0, 0.5);
    --radius: 4px;
    --radius-sm: 3px;
}

body {
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    margin: 0;
    -webkit-font-smoothing: antialiased;
    overflow-x: hidden;
}

/* Both themes use Sora (x-height 0.54). Pinning every font to that x-height keeps fallback fonts
   the same visual size while Sora loads, and leaves Sora itself unchanged.
   Set on * because form controls don't inherit font properties by default. */
*,
*::before,
*::after {
    font-size-adjust: 0.54;
}

#app {
    display: flex;
    flex-direction: column;
    height: 100vh;
}
</style>

<style scoped>
/* === NAV === */
nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 14px 48px;
    position: sticky;
    top: 0;
    background: color-mix(in srgb, var(--green-light) 80%, transparent);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    z-index: 100;
    border-bottom: 1px solid transparent;
    transition: border-color 0.3s;
}

nav.scrolled {
    border-bottom-color: var(--border);
}

.nav-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.logo {
    font-family: var(--serif);
    font-size: 1.5rem;
    letter-spacing: -0.02em;
    color: var(--text);
    text-decoration: none;
}

/* Outfit (light theme) reads much lighter than Sora (dark theme) at the same weight */
:root:not([data-theme="dark"]) .logo {
    font-weight: 600;
}

.menu-btn {
    display: none;
    width: 36px;
    height: 36px;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    background: var(--surface);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s;
}

.menu-btn:hover {
    border-color: var(--border-hover);
    color: var(--text);
}

.nav-right {
    display: flex;
    align-items: center;
    gap: 24px;
}

.visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}

.profile-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 100px;
    font-size: 0.82rem;
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
    font-family: var(--sans);
}

.profile-btn:hover {
    border-color: var(--border-hover);
    box-shadow: var(--shadow-sm);
}

.profile-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.profile-menu {
    position: relative;
    min-width: 0;
}

.profile-caret {
    flex-shrink: 0;
    transition: transform 0.2s;
}

.profile-caret.open {
    transform: rotate(180deg);
}

.profile-dropdown {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    min-width: 200px;
    max-width: calc(100vw - 32px);
    padding: 6px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    box-shadow: var(--shadow-lg);
    z-index: 300;
    box-sizing: border-box;
    animation: dropdownIn 0.15s ease-out;
}

@keyframes dropdownIn {
    from {
        opacity: 0;
        transform: translateY(-4px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.profile-dropdown-header {
    padding: 8px 10px 10px;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--border);
    font-size: 0.75rem;
    color: var(--text-secondary);
    line-height: 1.5;
    overflow-wrap: anywhere;
}

.profile-dropdown-header strong {
    color: var(--text);
    font-weight: 600;
    font-size: 0.82rem;
}

.profile-dropdown-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 9px 10px;
    background: transparent;
    border: none;
    border-radius: calc(var(--radius-sm) - 4px);
    font-family: var(--sans);
    font-size: 0.85rem;
    color: var(--text);
    cursor: pointer;
    text-align: left;
    transition: background 0.15s;
}

.profile-dropdown-item:hover,
.profile-dropdown-item:focus-visible {
    background: var(--chip-bg);
    outline: none;
}

.profile-dropdown-item:disabled {
    opacity: 0.6;
    cursor: default;
}

:root[data-theme="dark"] .profile-dropdown,
:root[data-theme="dark"] .profile-dropdown-item {
    border-radius: 4px;
}

.theme-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 100px;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
}

.theme-toggle:hover {
    border-color: var(--border-hover);
    color: var(--text);
    box-shadow: var(--shadow-sm);
}

.app-layout {
    display: flex;
    flex: 1;
    min-height: 0;
}

/* === MAIN === */
/* main is the full-width scroll container, so its scrollbar sits at the window edge
   instead of floating beside the centred content column */
main {
    flex: 1;
    overflow-y: auto;
    min-width: 0;
    min-height: 0;
    /* lets flex item shrink properly inside another flex container */
    scrollbar-width: thin;
    scrollbar-color: var(--border-hover) transparent;
}

main::-webkit-scrollbar {
    width: 8px;
}

main::-webkit-scrollbar-track {
    background: transparent;
}

main::-webkit-scrollbar-thumb {
    background: var(--border);
    border-radius: 8px;
}

main::-webkit-scrollbar-thumb:hover {
    background: var(--border-hover);
}

main::-webkit-scrollbar-button {
    display: none;
}

.main-inner {
    max-width: 1100px;
    margin: 0 auto;
    padding: 56px 24px 0;
    /* removed bottom padding — search bar handles it now */
    width: 100%;
    /* include padding in the 100% width, otherwise it overflows the viewport by its side padding */
    box-sizing: border-box;
    min-height: 100%;
    display: flex;
    flex-direction: column;
}


/* === SECTION LABELS === */
.section-label {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--text-secondary);
}

.section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
}

/* === UPLOAD ZONE === */
.upload-zone {
    border: 1.5px dashed var(--upload-border);
    border-radius: var(--radius);
    background: var(--upload-bg);
    padding: 20px 32px;
    text-align: center;
    cursor: pointer;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}

.upload-zone::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 50% 0%, rgba(58, 125, 68, 0.04), transparent 70%);
    opacity: 0;
    transition: opacity 0.3s;
}

.upload-zone:hover {
    border-color: var(--green);
    background: var(--green-light);
    box-shadow: var(--shadow-sm);
}

.upload-zone:hover::before {
    opacity: 1;
}

.upload-zone:hover .upload-icon {
    transform: translateY(-2px);
}

.upload-icon {
    width: 48px;
    height: 48px;
    margin: 0 auto 16px;
    border-radius: 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s;
    box-shadow: var(--shadow-sm);
}

.upload-icon svg {
    width: 20px;
    height: 20px;
    stroke: var(--text-secondary);
    transition: stroke 0.3s;
}

.upload-zone:hover .upload-icon svg {
    stroke: var(--green);
}

.upload-zone:hover .upload-icon {
    border-color: var(--green);
}

.upload-zone.signed-out {
    cursor: pointer;
}

.upload-zone.signed-out .upload-icon {
    opacity: 0.55;
}

.upload-link {
    color: var(--green);
    text-decoration: underline;
    text-underline-offset: 2px;
    font-weight: 500;
}

.upload-text {
    font-size: 0.92rem;
    font-weight: 500;
    color: var(--text);
    margin-bottom: 4px;
}

.upload-text-filename {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.upload-text span {
    color: var(--green);
    text-decoration: underline;
    text-underline-offset: 2px;
}

.upload-sub {
    font-size: 0.78rem;
    color: var(--text-secondary);
}

/* Chat section */
.chat {
    flex: 1;
    display: flex;
    flex-direction: column;
}

.chat-messages {
    display: flex;
    flex-direction: column;
    gap: 20px;
    margin-top: 8px;
    padding-bottom: 24px;
    flex: 1;
}

/* A new question starts a new exchange: give it more room than the gap inside one */
.message.user:not(:first-child) {
    margin-top: 16px;
}

.message {
    max-width: 65ch;
    padding: 14px 18px;
    border-radius: var(--radius);
    font-size: 0.9rem;
    line-height: 1.5;
}

/* Message text comes from v-html (markdown), which scoped styles don't reach, hence :deep().
   Paragraph margins are zeroed and spacing is added only *between* blocks, so bubbles have even padding. */
.message :deep(p) {
    margin: 0;
    overflow-wrap: break-word;
    word-break: break-word;
}

.message :deep(p + p),
.message :deep(p + ul),
.message :deep(p + ol),
.message :deep(ul + p),
.message :deep(ol + p),
.message :deep(h1 + p),
.message :deep(h2 + p),
.message :deep(h3 + p) {
    margin-top: 0.6em;
}

.message :deep(ul),
.message :deep(ol) {
    margin: 0;
    padding-left: 1.3em;
}

.message :deep(li + li) {
    margin-top: 0.3em;
}

.message :deep(h1),
.message :deep(h2),
.message :deep(h3) {
    margin: 0.9em 0 0;
    font-size: 0.95rem;
    font-weight: 600;
}

.message :deep(h1:first-child),
.message :deep(h2:first-child),
.message :deep(h3:first-child) {
    margin-top: 0;
}

.message :deep(code) {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85em;
    padding: 1px 5px;
    border-radius: 4px;
    background: rgba(127, 127, 127, 0.18);
}

.message :deep(p a),
.message :deep(li a) {
    color: inherit;
    text-decoration: underline;
    text-underline-offset: 2px;
}

.message.user {
    align-self: flex-end;
    background: var(--user-bubble);
    border: 1px solid var(--user-bubble-border);
    color: var(--text);
}

/* Plain-text answers are quiet panels; the lead cards are meant to be the visual focus */
.message.assistant {
    align-self: flex-start;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
}

.message.assistant.loading {
    align-self: flex-start;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-secondary);
}

.message.assistant.notice {
    align-self: flex-start;
    background: var(--surface);
    border: 1px solid var(--border);
    color: var(--text-secondary);
}

.message.assistant.error {
    align-self: flex-start;
    background: #FDEDEC;
    border: 1px solid #E8B4AE;
    color: #7A2E27;
}

:root[data-theme="dark"] .message.assistant.error {
    background: #2A1515;
    border-color: #6B2E2E;
    color: #F2A8A0;
}

/* === LOADER === */
.message.assistant.loading {
    width: min(100%, 540px);
    box-sizing: border-box;
    padding: 18px 20px;
    box-shadow: var(--shadow-sm);
}

.loader-head {
    display: flex;
    align-items: center;
    gap: 10px;
}

.loader-ring {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    animation: loaderSpin 0.9s linear infinite;
}

.loader-ring circle {
    fill: none;
    stroke-width: 3;
}

.loader-ring-track {
    stroke: var(--border);
}

.loader-ring-arc {
    stroke: var(--green);
    stroke-linecap: round;
    /* circumference ≈ 56.5: show roughly a quarter of the ring */
    stroke-dasharray: 16 56.5;
}

@keyframes loaderSpin {
    to {
        transform: rotate(360deg);
    }
}

.message .loader-label {
    flex: 1;
    min-width: 0;
    font-size: 0.92rem;
    font-weight: 600;
    color: var(--text);
}

.loader-bar {
    position: relative;
    height: 6px;
    margin: 14px 0 16px;
    border-radius: 100px;
    background: var(--chip-bg);
    overflow: hidden;
}

.loader-bar-fill {
    position: relative;
    height: 100%;
    border-radius: inherit;
    background: var(--green);
    transition: width 1s linear;
    overflow: hidden;
}

/* Light sweep across the filled part so the bar looks alive between its 1-second steps */
.loader-bar-fill::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.45), transparent);
    transform: translateX(-100%);
    animation: loaderSweep 1.6s ease-in-out infinite;
}

@keyframes loaderSweep {
    to {
        transform: translateX(100%);
    }
}

/* .message prefix outranks the markdown list rules (`.message :deep(ol)`, `:deep(li + li)`) */
.message .loader-steps {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
}

.message .loader-steps li {
    margin: 0;
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 0.8rem;
    color: var(--text-secondary);
    opacity: 0.7;
    transition: color 0.3s, opacity 0.3s;
}

.loader-steps li.active,
.loader-steps li.done {
    opacity: 1;
}

.loader-steps li.active {
    color: var(--text);
    font-weight: 600;
}

.loader-step-dot {
    flex-shrink: 0;
    width: 14px;
    height: 14px;
    box-sizing: border-box;
    border-radius: 50%;
    border: 1.5px solid var(--border-hover);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.3s, border-color 0.3s;
}

.loader-steps li.active .loader-step-dot {
    border-color: var(--green);
    background: var(--green-light);
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--green) 45%, transparent);
    animation: loaderPulse 1.6s ease-out infinite;
}

@keyframes loaderPulse {
    to {
        box-shadow: 0 0 0 6px transparent;
    }
}

.loader-steps li.done .loader-step-dot {
    border-color: var(--green);
    background: var(--green);
}

.loader-step-dot svg {
    width: 10px;
    height: 10px;
    fill: none;
    stroke: var(--surface);
    stroke-width: 3.5;
    stroke-linecap: round;
    stroke-linejoin: round;
}

.message .loading-meta {
    margin-top: 14px;
    font-size: 0.76rem;
    color: var(--text-secondary);
}

.loading-dots::after {
    content: '';
    display: inline-block;
    width: 1.2em;
    text-align: left;
    animation: loadingDots 1.2s steps(4, end) infinite;
}

@keyframes loadingDots {
    0% {
        content: '';
    }

    25% {
        content: '.';
    }

    50% {
        content: '..';
    }

    75% {
        content: '...';
    }
}

/* When assistant has lead cards, go full-width and transparent */
.message.assistant.has-leads {
    max-width: 100%;
    align-self: stretch;
    background: transparent;
    border: none;
    color: var(--text);
    padding: 0;
}

/* .message prefix: needs to outrank `.message :deep(p)`, which zeroes paragraph margins */
.message .personalized-badge {
    display: inline-block;
    margin-bottom: 12px;
    padding: 4px 12px;
    border-radius: 100px;
    background: var(--green-light);
    color: var(--green);
    font-size: 0.74rem;
    font-weight: 500;
}

.message .leads-summary {
    font-size: 0.95rem;
    color: var(--text);
    margin-bottom: 18px;
    line-height: 1.6;
}

.leads-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
    gap: 16px;
}

/* === LEAD CARD ===
   The heaviest thing in the conversation: raised surface, clear name → role → company → why → action order.
   `.message` prefixes outrank the markdown rules (`.message :deep(p)`, `:deep(h3)`) that share these tags. */
.lead-card {
    display: flex;
    flex-direction: column;
    padding: 20px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow-sm);
    transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;
}

.lead-card:hover {
    border-color: color-mix(in srgb, var(--green) 55%, var(--border));
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}

.lead-head {
    display: flex;
    align-items: flex-start;
    gap: 12px;
}

.lead-avatar {
    flex-shrink: 0;
    width: 42px;
    height: 42px;
    border-radius: 50%;
    background: var(--green-light);
    color: var(--green);
    font-family: var(--serif);
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Logos come in their own colors, so sit them on a plain white tile in both themes */
.lead-avatar.has-logo {
    background: #FFFFFF;
    border: 1px solid var(--border);
    box-sizing: border-box;
    overflow: hidden;
}

.lead-avatar img {
    width: 28px;
    height: 28px;
    object-fit: contain;
}

.lead-id {
    flex: 1;
    min-width: 0;
}

.message .lead-name {
    margin: 0 0 2px;
    font-family: var(--serif);
    font-size: 1.02rem;
    font-weight: 600;
    line-height: 1.3;
    color: var(--text);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.message .lead-title {
    margin: 0;
    font-size: 0.84rem;
    line-height: 1.4;
    color: var(--text);
    opacity: 0.85;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.message .lead-company {
    margin: 3px 0 0;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--green);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* While one card is open, cards in that grid keep their own height instead of
   stretching to the open card. Closed cards are all clamped to 3 lines, so they stay close in size. */
.leads-grid.has-open {
    align-items: start;
}

.lead-why {
    margin: 14px 0 18px;
}

.message .lead-relevance {
    margin: 0;
    font-size: 0.88rem;
    line-height: 1.6;
    color: var(--text);
    opacity: 0.8;
}

.message .lead-relevance.clamped {
    display: -webkit-box;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
}

.message .lead-more {
    margin-top: 6px;
    padding: 2px 0;
    background: none;
    border: none;
    font: inherit;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--green);
    cursor: pointer;
}

.message .lead-more:hover {
    text-decoration: underline;
}

.message .lead-more:focus-visible {
    outline: 2px solid var(--green);
    outline-offset: 2px;
    border-radius: 2px;
}

/* The open card is reading, not hovering: don't lift it */
.lead-card.open:hover {
    transform: none;
}

.lead-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 10px;
    margin-top: auto;
    padding-top: 14px;
    border-top: 1px solid var(--border);
}

/* A lead with neither an email nor a source has nothing to act on, so drop the empty footer */
.lead-actions:empty {
    display: none;
}

.lead-email-addr {
    flex: 1 1 0;
    min-width: 0;
    font-size: 0.78rem;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.lead-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 14px;
    font-size: 0.8rem;
    font-family: var(--sans);
    font-weight: 600;
    border-radius: 100px;
    text-decoration: none;
    transition: all 0.2s;
    cursor: pointer;
    white-space: nowrap;
}

.email-btn {
    background: var(--green);
    color: #fff;
}

:root[data-theme="dark"] .email-btn {
    color: var(--bg);
}

.email-btn:hover {
    filter: brightness(1.08);
}

.source-btn {
    margin-left: auto;
    background: transparent;
    color: var(--text);
    border: 1px solid var(--border-hover);
}

.source-btn:hover {
    border-color: var(--green);
    color: var(--green);
}

/* .search-fixed {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    margin-top: 0;
    padding: 16px 24px 24px;
    background: linear-gradient(transparent, var(--bg) 25%);
    z-index: 50;
    display: flex;
    flex-direction: column;
    align-items: center;
} */

.search-section {
    transition: margin-top 0.35s ease, padding 0.35s ease;
}

.search-fixed {
    margin-top: auto;
    position: sticky;
    bottom: 0;
    padding: 16px 0 max(24px, calc(env(safe-area-inset-bottom) + 8px));
    background: linear-gradient(transparent, var(--bg) 25%);
    z-index: 50;
}

.search-fixed .search-wrapper {
    width: 100%;
    max-width: 100%;
}


/* === SEARCH SECTION === */
.section-gap {
    margin-top: 40px;
}

.search-btn:disabled,
.search-input:disabled {
    opacity: 0.65;
    cursor: not-allowed;
}

.search-btn:disabled:hover {
    transform: none;
    background: var(--accent);
}

.search-wrapper {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    margin-bottom: 16px;
}

.search-input {
    flex: 1;
    min-width: 0;
    /* lets the flex item shrink properly */
    box-sizing: border-box;
    /* the actual fix for the overflow */
    padding: 16px 20px;
    /* removed the extra right padding that made room for the button */
    font-family: var(--sans);
    font-size: 0.95rem;
    color: var(--text);
    background: var(--surface);
    border: 1.5px solid var(--border);
    border-radius: var(--radius);
    outline: none;
    transition: all 0.25s;
    box-shadow: var(--shadow-sm);
}

/* Input + pin share one box; the pin sits inside the input's right edge */
.search-field {
    position: relative;
    flex: 1;
    min-width: 0;
    display: flex;
}

.search-field .search-input {
    width: 100%;
    /* room for the pin button */
    padding-right: 52px;
}

.attach-btn {
    position: absolute;
    top: 50%;
    right: 8px;
    transform: translateY(-50%);
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0;
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
    transition: color 0.15s, background 0.15s;
}

.attach-btn:hover:not(:disabled) {
    color: var(--green);
    background: var(--chip-bg);
}

.attach-btn:focus-visible {
    outline: 2px solid var(--green);
    outline-offset: 0;
}

.attach-btn:disabled {
    opacity: 0.5;
    cursor: progress;
}

:root[data-theme="dark"] .attach-btn {
    border-radius: 4px;
}

/* Status line above the input for an upload started from the pin */
.attach-status {
    display: flex;
    align-items: center;
    gap: 8px;
    max-width: 100%;
    width: fit-content;
    box-sizing: border-box;
    margin-bottom: 10px;
    padding: 7px 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 100px;
    box-shadow: var(--shadow-sm);
    font-size: 0.8rem;
    color: var(--green);
    animation: dropdownIn 0.15s ease-out;
}

.attach-status.uploading {
    color: var(--text-secondary);
}

.attach-status.error {
    color: #B3261E;
    border-color: #E8B4AE;
    background: #FDEDEC;
}

:root[data-theme="dark"] .attach-status {
    border-radius: 4px;
}

:root[data-theme="dark"] .attach-status.error {
    color: #F2A8A0;
    border-color: #6B2E2E;
    background: #2A1515;
}

.attach-status svg {
    flex-shrink: 0;
}

.attach-name {
    min-width: 0;
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 600;
    color: var(--text);
}

.attach-note {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.attach-spinner {
    width: 14px;
    height: 14px;
    animation: loaderSpin 0.9s linear infinite;
}

.attach-spinner circle {
    fill: none;
    stroke: var(--green);
    stroke-width: 3;
    stroke-linecap: round;
    stroke-dasharray: 16 56.5;
}

.attach-dismiss {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    margin-right: -4px;
    background: transparent;
    border: none;
    border-radius: 50%;
    color: inherit;
    cursor: pointer;
}

.attach-dismiss:hover {
    background: rgba(127, 127, 127, 0.18);
}

.search-input::placeholder {
    color: #B0ADA6;
}

.search-input:focus {
    border-color: var(--accent);
    box-shadow: var(--shadow-md), 0 0 0 3px rgba(44, 44, 44, 0.22);
}

:root[data-theme="dark"] .search-input:focus {
    box-shadow: var(--shadow-md), 0 0 0 3px rgba(230, 233, 240, 0.18);
}

.search-btn {
    flex-shrink: 0;
    /* prevents the button from collapsing */
    width: 48px;
    height: 48px;
    background: var(--accent);
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.search-btn:hover {
    background: #000;
    transform: scale(1.05);
    /* was translateY(-50%) scale(1.05) — no longer needed */
}

.search-btn svg {
    width: 16px;
    height: 16px;
    stroke: #fff;
}

/* === CHIPS === */
.chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.chip {
    padding: 8px 16px;
    background: var(--chip-bg);
    border: 1px solid transparent;
    border-radius: 100px;
    font-family: var(--sans);
    font-size: 0.8rem;
    font-weight: 450;
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}

.chip:hover {
    background: var(--chip-hover);
    border-color: var(--border);
    color: var(--text);
}

:root[data-theme="dark"] .chip,
:root[data-theme="dark"] .lead-btn,
:root[data-theme="dark"] .profile-btn,
:root[data-theme="dark"] .theme-toggle {
    border-radius: 4px;
}

/* === HERO FOOTER === */
.hero-section {
    text-align: center;
    padding: 0 0 24px;
    position: relative;
}

.hero-title {
    font-family: var(--serif);
    font-size: 2.6rem;
    font-weight: 400;
    letter-spacing: -0.02em;
    line-height: 1.2;
    margin-bottom: 16px;
    color: var(--text);
}

.hero-title em {
    font-style: normal;
    font-weight: 600;
    color: var(--green);
}

.hero-sub {
    font-size: 0.95rem;
    color: var(--text-secondary);
    line-height: 1.65;
    max-width: 420px;
    margin: 0 auto;
    font-weight: 300;
}

/* === ANIMATIONS === */
@keyframes fadeUp {
    from {
        opacity: 0;
        transform: translateY(16px);
    }

    to {
        opacity: 1;
        transform: translateY(0);
    }
}

.fade-in {
    animation: fadeUp 0.6s ease-out both;
}

.fade-in-1 {
    animation-delay: 0.05s;
}

.fade-in-2 {
    animation-delay: 0.15s;
}

.fade-in-3 {
    animation-delay: 0.25s;
}

.fade-in-4 {
    animation-delay: 0.40s;
}

/* === FOCUS === */
.menu-btn:focus-visible,
.profile-btn:focus-visible,
.search-btn:focus-visible,
.chip:focus-visible,
.lead-btn:focus-visible,
.upload-zone:focus-visible {
    outline: 2px solid var(--green);
    outline-offset: 2px;
}

/* === REDUCED MOTION === */
@media (prefers-reduced-motion: reduce) {

    .fade-in,
    .fade-in-1,
    .fade-in-2,
    .fade-in-3,
    .fade-in-4 {
        animation: none;
    }

    .loading-dots::after {
        animation: none;
        content: '...';
    }

    .loader-ring,
    .attach-spinner,
    .loader-bar-fill::after,
    .loader-steps li.active .loader-step-dot {
        animation: none;
    }

    .loader-bar-fill {
        transition: none;
    }

    .upload-zone,
    .upload-icon,
    .search-btn,
    .chip,
    .lead-card,
    .lead-btn,
    .history-panel {
        transition: none;
    }
}

/* === RESPONSIVE === */

/* Coarse pointers (touch) need bigger hit areas than a precise mouse cursor */
@media (pointer: coarse) {

    .chip,
    .lead-btn {
        min-height: 44px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }

    .profile-btn,
    .menu-btn {
        min-height: 44px;
    }
}

/* Tablet: sidebar pushes content with less margin to spare than desktop */
@media (min-width: 768px) and (max-width: 1023px) {
    .main-inner {
        padding: 48px 20px 0;
    }
}

@media (max-width: 767px) {
    nav {
        padding: 12px 20px;
        padding-left: max(20px, env(safe-area-inset-left));
        padding-right: max(20px, env(safe-area-inset-right));
    }

    .menu-btn {
        display: flex;
    }

    .main-inner {
        padding: 40px 20px 80px;
        padding-left: max(20px, env(safe-area-inset-left));
        padding-right: max(20px, env(safe-area-inset-right));
    }

    .hero-title {
        font-size: 2rem;
    }

    .upload-zone {
        padding: 36px 20px;
    }
}

@media (max-width: 640px) {
    .leads-grid {
        grid-template-columns: 1fr;
    }
}

/* Small phones (iPhone SE / mini, most Androids ≤ 400px) */
@media (max-width: 420px) {
    nav {
        padding: 10px 16px;
        padding-left: max(16px, env(safe-area-inset-left));
        padding-right: max(16px, env(safe-area-inset-right));
        gap: 8px;
    }

    .nav-left {
        gap: 8px;
        min-width: 0;
    }

    .logo {
        font-size: 1.3rem;
    }

    .nav-right {
        gap: 8px;
        min-width: 0;
    }

    .profile-btn {
        padding: 8px 12px;
        max-width: 132px;
        min-width: 0;
    }

    .profile-menu .profile-btn {
        max-width: 148px;
    }

    .main-inner {
        padding: 32px 16px 72px;
        padding-left: max(16px, env(safe-area-inset-left));
        padding-right: max(16px, env(safe-area-inset-right));
    }

    .hero-title {
        font-size: 1.75rem;
    }

    .hero-sub {
        font-size: 0.9rem;
    }

    .upload-zone {
        padding: 28px 16px;
    }

    .search-wrapper {
        gap: 8px;
    }

    .search-input {
        padding: 14px 16px;
        /* 16px keeps iOS Safari from zooming in when the field gets focus */
        font-size: 16px;
    }

    .search-btn {
        width: 48px;
        height: 48px;
    }

    .chip {
        white-space: normal;
        max-width: 100%;
        box-sizing: border-box;
    }
}
</style>