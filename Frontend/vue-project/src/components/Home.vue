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
            <button class="profile-btn" @click="login">
                <span class="profile-dot" :style="userName ? 'background: var(--green)' : ''"></span>
                {{ userName || 'Login' }}
            </button>
        </div>
    </nav>

    <div class="app-layout">
        <ChatHistory ref="historyRef" :userId="userId" :activeSessionId="currentSessionId" @select-chat="loadChat"
            @new-chat="startNewChat" @session-expired="clearUser" />

        <main>

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
                    :aria-label="!userId ? 'Sign in with Google to upload your resume.' : (fileName ? `Resume uploaded: ${fileName}. Press Enter to replace it.` : 'Upload your resume. PDF, DOC, or DOCX, up to 10 megabytes.')"
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
                    <p class="upload-sub" v-else-if="!fileName">Optional — PDF, DOC, or DOCX, up to 10MB. You can
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
                            <p class="loading-status" role="status" aria-live="polite">
                                {{ msg.text }}<span class="loading-dots" aria-hidden="true"></span>
                            </p>
                            <p class="loading-meta">
                                {{ formatElapsed(elapsedSeconds) }}
                                <span v-if="elapsedSeconds < 90"> · usually takes 30–90s</span>
                                <span v-else> · still working, this one's taking longer than usual</span>
                            </p>
                        </template>

                        <!-- Assistant with leads: show cards -->
                        <template v-else-if="msg.leads && msg.leads.length">
                            <p v-if="msg.personalized" class="personalized-badge">Personalized using your résumé</p>
                            <p v-if="msg.text" class="leads-summary">{{ msg.text }}</p>
                            <div class="leads-grid">
                                <div v-for="(lead, j) in msg.leads" :key="j" class="lead-card">
                                    <!-- <div class="lead-avatar">{{ lead.name?.charAt(0) || '?' }}</div> -->
                                    <div class="lead-info">
                                        <div class="lead-name" :title="lead.name || 'Unnamed contact'">{{ lead.name
                                            || 'Unnamed contact' }}</div>
                                        <div class="lead-title" v-if="lead.title || lead.company"
                                            :title="[lead.title, lead.company].filter(Boolean).join(' @ ')">{{
                                                lead.title }} <span v-if="lead.company">@ {{
                                                lead.company }}</span></div>
                                        <p class="lead-relevance" v-if="lead.relevance">{{ lead.relevance }}</p>
                                        <div class="lead-actions">
                                            <a v-if="lead.email" :href="'mailto:' + lead.email"
                                                class="lead-btn email-btn">✉ Email</a>
                                            <span v-else class="lead-no-email">No direct email found</span>
                                            <a v-if="lead.source_url" :href="lead.source_url" target="_blank"
                                                rel="noopener noreferrer" class="lead-btn source-btn">↗ Source</a>
                                        </div>
                                    </div>
                                </div>
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
                <div class="search-wrapper">
                    <input class="search-input" type="text" placeholder="Find somebody to reach out to..."
                        v-model="searchQuery" id="search-input" @keydown.enter="getQueryResponse"
                        :disabled="isLoading">
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

        </main>

    </div>
</template>

<script setup>
import { ref, onMounted, nextTick, onBeforeUnmount } from 'vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { v4 as uuidv4 } from 'uuid';
import ChatHistory from './ChatHistory.vue'

const API_BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 30000;
const MAX_RESUME_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_RESUME_TYPES = ['.pdf', '.doc', '.docx'];

function renderMarkdown(text) {
    return DOMPurify.sanitize(marked.parse(text ?? '', { breaks: true }));
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

const searchQuery = ref('')
const isScrolled = ref(false)
const userName = ref('')

const fileInput = ref(null);
const fileName = ref('')
const resumeFile = ref(null);
const uploadError = ref('');
const isUploading = ref(false);
const hasResume = ref(false);
let personalizedNoticeShown = false;
const querySubmitted = ref(false);
const messages = ref([]);

const userId = ref('')

const currentSessionId = ref(uuidv4());

const historyRef = ref(null);
const chatSectionRef = ref(null);
const isLoading = ref(false);
const elapsedSeconds = ref(0);
let loadingStatusTimer = null;
let elapsedTimer = null;

function statusForQuery(query) {
    const q = query.toLowerCase();
    if (/\b(startup|startups|compan(?:y|ies)|organizations?|hiring)\b/.test(q)) {
        return ['Finding companies...', 'Scanning the web...', 'Ranking matches...'];
    }
    if (/\b(who|engineer|engineers|people|person|lead|leads|manager|hire|recruit)\b/.test(q)) {
        return ['Finding leads', 'Searching the web', 'Personalizing matches'];
    }
    return ['Generating response...', 'Thinking...', 'Putting it together...'];
}

function formatElapsed(totalSeconds) {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}:${String(secs).padStart(2, '0')}`;
}

function clearLoadingStatusTimer() {
    if (loadingStatusTimer) {
        clearInterval(loadingStatusTimer);
        loadingStatusTimer = null;
    }
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

    const formData = new FormData();
    formData.append('file', resumeFile.value);

    try {
        const res = await fetchWithTimeout(`${API_BASE}/uploadResume`, {
            method: 'POST',
            body: formData
        });

        if (res.status === 401) {
            clearUser();
            throw new Error('unauthorized');
        }
        if (!res.ok) throw new Error(`Server returned ${res.status}`);
        await res.json();
        hasResume.value = true;
    } catch (err) {
        console.error('Resume upload failed:', err);
        uploadError.value = err.name === 'AbortError'
            ? 'Upload timed out. Please try again.'
            : err.message === 'unauthorized'
                ? 'Your sign-in expired. Sign in with Google again to upload your resume.'
                : 'Upload failed. Please try again.';
        resumeFile.value = null;
        fileName.value = '';
        if (fileInput.value) fileInput.value.value = '';
    } finally {
        isUploading.value = false;
    }
}

function validateResumeFile(file) {
    if (!hasAllowedExtension(file.name)) {
        uploadError.value = 'Unsupported file type. Please upload a PDF, DOC, or DOCX.';
        return false;
    }
    if (file.size > MAX_RESUME_SIZE) {
        uploadError.value = 'File is too large. Maximum size is 10MB.';
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

    const statuses = statusForQuery(query);
    let statusIndex = 0;
    messages.value.push({ role: "assistant", text: statuses[0], loading: true });
    loadingStatusTimer = setInterval(() => {
        statusIndex = (statusIndex + 1) % statuses.length;
        const loadingMsg = messages.value.find((msg) => msg.loading);
        if (loadingMsg) loadingMsg.text = statuses[statusIndex];
    }, 2800);
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
        });

        if (response.status === 401) {
            clearUser();
            removeLoadingMessages();
            messages.value.push({ role: "assistant", text: SIGN_IN_PROMPT, leads: [], notice: true });
            return;
        }
        if (!response.ok) throw new Error(`Server returned ${response.status}`);

        const data = await response.json();
        let leads = Array.isArray(data.leads) ? data.leads : [];
        let text = data.response || data.suggestions || "";

        if (!leads.length && typeof text === "string") {
            let cleaned = text.trim();
            if (cleaned.startsWith("```")) cleaned = cleaned.split("\n").slice(1).join("\n");
            if (cleaned.endsWith("```")) cleaned = cleaned.slice(0, cleaned.lastIndexOf("```"));
            cleaned = cleaned.trim();
            try {
                const parsed = JSON.parse(cleaned);
                if (Array.isArray(parsed.leads)) {
                    leads = parsed.leads;
                    text = parsed.summary || parsed.suggestions || "";
                }
            } catch (err) {
                // not JSON — show the text as-is
            }
        }

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
                : "Something went wrong while searching. Please try again.",
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
        messages.value = (data.messages || []).map(m => ({
            role: m.role,
            text: m.content,
            leads: Array.isArray(m.leads) ? m.leads : []
        }))
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
    --serif: 'Outfit', -apple-system, sans-serif;
    --sans: 'Karla', -apple-system, sans-serif;
    --shadow-sm: 0 1px 2px rgba(30, 35, 45, 0.06), 0 1px 3px rgba(30, 35, 45, 0.04);
    --shadow-md: 0 4px 12px rgba(30, 35, 45, 0.09), 0 1px 4px rgba(30, 35, 45, 0.05);
    --shadow-lg: 0 14px 36px rgba(30, 35, 45, 0.12), 0 4px 12px rgba(30, 35, 45, 0.06);
    --radius: 17px;
    --radius-sm: 12.5px;
}

body {
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    margin: 0;
    -webkit-font-smoothing: antialiased;
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

.profile-dot {
    width: 8px;
    height: 8px;
    background: var(--border);
    border-radius: 50%;
}

.app-layout {
    display: flex;
    flex: 1;
    min-height: 0;
}

/* === MAIN === */
main {
    flex: 1;
    overflow-y: auto;
    max-width: 1100px;
    margin: 0 auto;
    padding: 56px 24px 0;
    /* removed bottom padding — search bar handles it now */
    width: 100%;
    display: flex;
    /* new */
    flex-direction: column;
    /* new */
    min-height: 0;
    /* new — lets flex item shrink properly inside another flex container */
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
    gap: 16px;
    margin-top: 8px;
    padding-bottom: 24px;
    flex: 1;
}

.message {
    max-width: 65ch;
    padding: 14px 18px;
    border-radius: var(--radius);
    font-size: 0.9rem;
    line-height: 1.5;
}

.message p {
    margin: 0;
    overflow-wrap: break-word;
    word-break: break-word;
}

.message.user {
    align-self: flex-end;
    background: var(--chip-bg);
    border: 1px solid var(--border);
    color: var(--text);
}

.message.assistant {
    align-self: flex-start;
    background: var(--accent);
    color: #fff;
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

.loading-status {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    font-style: italic;
}

.message .loading-meta {
    margin-top: 4px;
    font-size: 0.76rem;
    font-variant-numeric: tabular-nums;
    color: var(--text-secondary);
    opacity: 0.85;
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
    color: var(--text);
    padding: 0;
}

.personalized-badge {
    display: inline-block;
    margin-bottom: 10px;
    padding: 4px 12px;
    border-radius: 100px;
    background: var(--green-light);
    color: var(--green);
    font-size: 0.74rem;
    font-weight: 500;
}

.leads-summary {
    font-size: 0.88rem;
    color: var(--text-secondary);
    margin-bottom: 22px;
    line-height: 1.5;
}

.leads-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
    gap: 12px;
}

.lead-card {
    display: flex;
    gap: 14px;
    padding: 18px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    transition: border-color 0.2s, box-shadow 0.2s;
}

.lead-card:hover {
    border-color: var(--green);
    box-shadow: var(--shadow-md);
}

.lead-avatar {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--green-light, #E8F5E9);
    color: var(--green);
    font-family: var(--serif);
    font-size: 1.1rem;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
}

.lead-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
}

.lead-name {
    font-weight: 600;
    font-size: 0.92rem;
    color: var(--text);
    margin-bottom: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.lead-title {
    font-size: 0.8rem;
    color: var(--text-secondary);
    margin-bottom: 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.lead-title span {
    color: var(--green);
    font-weight: 500;
}

.lead-relevance {
    font-size: 0.78rem;
    color: var(--text-secondary);
    line-height: 1.5;
    margin-bottom: 10px;
}

.lead-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: auto;
}

.lead-no-email {
    font-size: 0.72rem;
    font-style: italic;
    color: var(--text-secondary);
    opacity: 0.8;
}

.lead-btn {
    padding: 5px 12px;
    font-size: 0.75rem;
    font-family: var(--sans);
    font-weight: 500;
    border-radius: 100px;
    text-decoration: none;
    transition: all 0.2s;
    cursor: pointer;
}

.email-btn {
    background: var(--green);
    color: #fff;
}

.email-btn:hover {
    opacity: 0.85;
}

.source-btn {
    background: var(--chip-bg);
    color: var(--text-secondary);
    border: 1px solid var(--border);
}

.source-btn:hover {
    border-color: var(--accent);
    color: var(--text);
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

.search-input::placeholder {
    color: #B0ADA6;
}

.search-input:focus {
    border-color: var(--accent);
    box-shadow: var(--shadow-md), 0 0 0 3px rgba(44, 44, 44, 0.22);
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
    main {
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

    main {
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
</style>