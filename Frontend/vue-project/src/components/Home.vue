    <template>

        <nav id="navbar" :class="{ scrolled: isScrolled }">
            <a href="/" class="logo">Reacher</a>
            <div class="nav-right">
                <a href="#" class="nav-link">Home</a>
                <button class="profile-btn" @click="login">
                    <span class="profile-dot" :style="userName ? 'background: var(--green)' : ''"></span>
                    {{ userName || 'Login' }}
                </button>
            </div>
        </nav>

        <div class="app-layout">
        <ChatHistory ref="historyRef" :userId="userId" :activeSessionId="currentSessionId" @select-chat="loadChat" @new-chat="startNewChat" />

        <main>

            <!-- Upload Section -->
            <section class="fade-in fade-in-1" v-if="!querySubmitted">
                <div class="section-label">01 — Your Profile</div>
                <div class="upload-zone" id="dropzone" @click="uploadResume()" @dragover.prevent @dragenter.prevent
                    @drop.prevent="handleDrop"
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
                    <p class="upload-text" v-if="!fileName">Drop your resume here or <span>browse</span></p>
                    <p class="upload-text" v-else style="color: var(--green)">{{ fileName }}</p>
                    <p class="upload-sub" v-if="!fileName">PDF, DOC, or DOCX</p>
                    <p class="upload-sub" v-else>
                        Resume uploaded
                        <span style="color: var(--green); cursor: pointer; text-decoration: underline;"
                            @click.stop="clearFile">Remove</span>
                    </p>

                    <input type="file" ref="fileInput" @change="handleFile" accept=".pdf,.doc,.docx"
                        style="display: none">
                </div>
            </section>

            <!-- Chat Section -->
            <section class="chat" v-if="querySubmitted">
                <div class="chat-messages">
                    <div v-for="(msg, i) in messages" :key="i" class="message" :class="msg.role">
                        <p v-html="marked(msg.text)"></p>
                    </div>
                </div>
            </section>

            <!-- Search Section -->
            <section class="section-gap fade-in fade-in-2" :class="['section-gap', 'fade-in', 'fade-in-2', {'search-fixed': querySubmitted}]">
                <div class="section-label" v-if="!querySubmitted">02 — What are you looking for?</div>
                <div class="search-wrapper">
                    <input class="search-input" type="text" placeholder="Find somebody to reach out to..."
                        v-model="searchQuery" id="search-input">
                    <button class="search-btn" @click="getQueryResponse">
                        <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round"
                            stroke-linejoin="round">
                            <line x1="22" y1="2" x2="11" y2="13" />
                            <polygon points="22 2 15 22 11 13 2 9 22 2" />
                        </svg>
                    </button>
                </div>

                <div class="chips" id="chips" v-if="!querySubmitted">
                    <span class="chip" @click="fillSearch('Find ML engineers at Nvidia')">Find ML engineers at
                        Nvidia</span>
                    <span class="chip" @click="fillSearch('Cybersecurity startups hiring in DC')">Cybersecurity startups
                        hiring in DC</span>
                    <span class="chip" @click="fillSearch('Who leads backend eng at Stripe?')">Who leads backend eng at
                        Stripe?</span>

                </div>
            </section>

            <!-- Hero -->
            <section class="hero-section fade-in fade-in-4" v-if="!querySubmitted">
                <h1 class="hero-title">Find people. <em>Reach them.</em></h1>
                <p class="hero-sub">Upload your resume to get started. Reacher uses your profile to find the right
                    people
                    and craft emails that get replies.</p>
            </section>

        </main>

    </div>
    </template>

<script setup>
import { ref, onMounted } from 'vue';
import { marked } from 'marked';
import {v4 as uuidv4} from 'uuid';
import ChatHistory from './ChatHistory.vue'

const searchQuery = ref('')
const isScrolled = ref(false)
const userName = ref('')

const fileInput = ref(null);
const fileName = ref('')
const resumeFile = ref(null);
const querySubmitted = ref(false);
const messages = ref([]);

const params = new URLSearchParams(window.location.search);
const userId = ref(params.get('email') || '')

const currentSessionId = ref(uuidv4());

const historyRef = ref(null);


onMounted(() => {
    window.addEventListener('scroll', () => {
        isScrolled.value = window.scrollY > 10
    })

    const params = new URLSearchParams(window.location.search)
    const name = params.get('name')
    const email = params.get('email')
    
    if (name && email) {
        userName.value = name;
        userId.value = email;

        localStorage.setItem('userName', name);
        localStorage.setItem('userId', email);
        window.history.replaceState({}, '', '/')
    }else{
        userName.value = localStorage.getItem('userName') || '';
        userId.value = localStorage.getItem('userId') || '';
    }
})

function fillSearch(text) {
    searchQuery.value = text
}

function login() {
    window.location.href = `${import.meta.env.VITE_BACKEND_URL}/auth/google`;
}

function uploadResume() {
    fileInput.value.click();
}

function startNewChat(){
    currentSessionId.value = uuidv4();
    messages.value = [];
    querySubmitted.value = false;
}

function handleFile(event) {
    const file = event.target.files[0];
    if (file) {
        resumeFile.value = file
        fileName.value = file.name
    }
}

function handleDrop(event) {
    const file = event.dataTransfer.files[0];
    if (file) {
        resumeFile.value = file;
        fileName.value = file.name;
    }
}

async function getQueryResponse(event){
    // let query = document.getElementById("search-input").value
    console.log(searchQuery.value);
    let query = searchQuery.value;
    // document.getElementById("chips").style.display = "none";
    querySubmitted.value = true;
    
    messages.value.push({"role": "user", "text": query});

     const response = await fetch(`${import.meta.env.VITE_BACKEND_URL}/processQuery`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            session_id: currentSessionId.value,
            user_id: userId.value,
            message: query
        })
        
    })


    // let data = "Found 9 ML Engineers at NVIDIA:\n\n1. **Rasoul Shafipour** - Senior AI/ML Engineer\n   - Previous: AI/ML Research Scientist at Apple\n   - LinkedIn: linkedin.com/in/rshafipour\n\n2. **Jonathan Mitchell** - Senior Machine Learning Engineer\n   - PhD from UCLA in Generative Modeling\n   - Specialization: BioNeMo and NIMs, Computer Vision\n   - LinkedIn: linkedin.com/in/jonathancmitchell\n\n3. **Nigel Nelson** - Senior Machine Learning Engineer\n   - Education: Milwaukee School of Engineering\n   - LinkedIn: linkedin.com/in/nigel-nelson-nvidia\n\n4. **Aqeel Anwar** - Senior ML Engineer\n   - Specialization: Autonomous Vehicles, perception networks\n   - Education: Georgia Tech, Previous: Samsung\n   - LinkedIn: linkedin.com/in/aqeelanwarmalik\n\n5. **Sean Huver** - Sr. Research Manager\n   - Specialization: AI healthcare workflows, NVIDIA Holoscan\n   - Education: UCLA\n   - LinkedIn: linkedin.com/in/sean-huver-53901171\n\n6. **Jeremy Jordan** - Senior ML Engineer, Information Retrieval\n   - Tenure: May 2024 - Present\n   - Previous: Data Scientist at Proofpoint\n   - LinkedIn: linkedin.com/in/jeremytjordan\n\n7. **Jeremy Dyer** - Principal Engineer\n   - Focus: High-performance, open-source systems, AI and large-scale document processing\n   - LinkedIn: linkedin.com/in/jeremy-dyer-a2969447\n\n8. **Matt Linder** - ML Engineer\n   - Education: San Francisco Conservatory of Music\n   - LinkedIn: linkedin.com/in/matt-linder-ml\n\n9. **Lakshmi Ramesh** - ML Engineer\n   - Experience: 2.5+ years in deep learning\n   - Location: Santa Clara, California\n   - LinkedIn: linkedin.com/in/rlakshmi24\n\nNote: NVIDIA also has 1,000+ open Machine Learning Engineer positions in the United States."

    const data = await response.json();
    console.log(data);

    messages.value.push({"role": "assistant", "text": data.response});

    if(!currentSessionId.value){
        currentSessionId.value = data.session_id
    }
    searchQuery.value = '';

    historyRef.value?.refresh()
}

function clearFile(){
    resumeFile.value = null;
    fileName.value = ''
    fileInput.value.value = "";
}

async function loadChat(sessionId){
    currentSessionId.value = sessionId;
    querySubmitted.value = true;
    messages.value = []

    try{
        const res = await fetch(`${import.meta.env.VITE_BACKEND_URL}/chat/${sessionId}`);

        const data = await res.json();
        messages.value = (data.messages || []).map(m => ({
            role: m.role,
            text: m.content
        }))
    } catch (err){
        console.log("Error loading chats")
    }
}

</script>

<style>
:root {
    --bg: #FAFAF8;
    --surface: #FFFFFF;
    --text: #1A1A1A;
    --text-secondary: #6B6B6B;
    --accent: #2C2C2C;
    --border: #E4E2DD;
    --border-hover: #C8C5BD;
    --chip-bg: #F2F1EE;
    --chip-hover: #E8E6E1;
    --upload-bg: #F7F6F3;
    --upload-border: #D8D5CE;
    --green: #3A7D44;
    --green-light: #EDF5EE;
    --serif: 'DM Serif Display', Georgia, serif;
    --sans: 'DM Sans', -apple-system, sans-serif;
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.03);
    --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.06), 0 1px 4px rgba(0, 0, 0, 0.04);
    --shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04);
    --radius: 12px;
    --radius-sm: 8px;
}

body {
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
}
</style>

<style scoped>
/* === NAV === */
nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 48px;
    position: sticky;
    top: 0;
    background: rgba(250, 250, 248, 0.85);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    z-index: 100;
    border-bottom: 1px solid transparent;
    transition: border-color 0.3s;
}

nav.scrolled {
    border-bottom-color: var(--border);
}

.logo {
    font-family: var(--serif);
    font-size: 1.5rem;
    letter-spacing: -0.02em;
    color: var(--text);
    text-decoration: none;
}

.nav-right {
    display: flex;
    align-items: center;
    gap: 24px;
}

.nav-link {
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-decoration: none;
    letter-spacing: 0.01em;
    transition: color 0.2s;
}

.nav-link:hover {
    color: var(--text);
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
    height: calc(100vh - 65px); /* subtract nav height */
}

/* === MAIN === */
main {
    flex: 1;
    overflow-y: auto;
    max-width: 720px;
    margin: 0 auto;
    padding: 56px 24px 140px;
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
    padding: 48px 32px;
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

.upload-text {
    font-size: 0.92rem;
    font-weight: 500;
    color: var(--text);
    margin-bottom: 4px;
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
.chat-messages{
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-top: 32px;
}

.message{
    max-width: 75%;
    padding: 14px 18px;
    border-radius: var(--radius);
    font-size: 0.9rem;
    line-height: 1.6;
    white-space: pre-wrap;
}

.message.user{
    align-self: flex-start;
    background: var(--chip-bg);
    border: 1px solid var(--border);
    color: var(--text);
}

.message.assistant{
    align-self: flex-end;
    background: var(--accent);
    color: #fff;
}

.search-fixed {
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
}

.search-fixed .search-wrapper {
    width: 100%;
    max-width: 720px;
}


/* === SEARCH SECTION === */
.section-gap {
    margin-top: 56px;
}

.search-wrapper {
    position: relative;
    margin-bottom: 16px;
}

.search-input {
    width: 100%;
    padding: 16px 56px 16px 20px;
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
    box-shadow: var(--shadow-md), 0 0 0 3px rgba(44, 44, 44, 0.06);
}

.search-btn {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    width: 38px;
    height: 38px;
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
    transform: translateY(-50%) scale(1.05);
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
    margin-top: 100px;
    text-align: center;
    padding: 64px 0;
    position: relative;
}

.hero-section::before {
    content: '';
    position: absolute;
    top: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 200px;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--border), transparent);
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
    font-style: italic;
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

/* === RESPONSIVE === */
@media (max-width: 640px) {
    nav {
        padding: 16px 20px;
    }

    main {
        padding: 40px 20px 80px;
    }

    .hero-title {
        font-size: 2rem;
    }

    .upload-zone {
        padding: 36px 20px;
    }
}
</style>