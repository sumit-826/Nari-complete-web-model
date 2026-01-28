// State Management
let currentChatId = null;
let selectedModel = 'Fast';

// BACKEND API SERVICE LAYER
// This class connects to the Flask/SQLite backend.
class BackendService {
    constructor() {
        this.baseUrl = 'http://localhost:5000/api';
    }

    // Load chat history from SQLite via Flask API
    async loadHistory() {
        try {
            const response = await fetch(`${this.baseUrl}/history`);
            if (!response.ok) throw new Error('Failed to load history');
            return await response.json();
        } catch (error) {
            console.error('Error loading history:', error);
            // Fallback to localStorage if backend unavailable
            const data = localStorage.getItem('nari_chats');
            return data ? JSON.parse(data) : [];
        }
    }

    // Save chat history to SQLite via Flask API
    async saveHistory(history) {
        try {
            const response = await fetch(`${this.baseUrl}/history`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(history)
            });
            if (!response.ok) throw new Error('Failed to save history');
            return await response.json();
        } catch (error) {
            console.error('Error saving history:', error);
            // Fallback to localStorage
            localStorage.setItem('nari_chats', JSON.stringify(history));
        }
    }

    // Send message to AI via Flask API (Nova LLM integration)
    async sendMessage(text, model, attachments = [], chatId = null) {
        try {
            const response = await fetch(`${this.baseUrl}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, model, attachments, chat_id: chatId })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to send message');
            }

            return await response.json();
        } catch (error) {
            console.error('Error sending message:', error);
            // Return fallback response if backend unavailable
            return {
                content: "Sorry, I couldn't connect to the AI service. Please ensure the backend is running.",
                processSteps: false
            };
        }
    }

    // Upload file via Flask API
    async uploadFile(file, type = 'document') {
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('type', type);

            const response = await fetch(`${this.baseUrl}/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Failed to upload file');
            return await response.json();
        } catch (error) {
            console.error('Error uploading file:', error);
            return { success: false, error: error.message };
        }
    }

    // Delete chat via Flask API
    async deleteChat(id) {
        try {
            const response = await fetch(`${this.baseUrl}/history/${id}`, {
                method: 'DELETE'
            });
            if (!response.ok) throw new Error('Failed to delete chat');
            return true;
        } catch (error) {
            console.error('Error deleting chat:', error);
            return false;
        }
    }

    // Check backend health
    async checkHealth() {
        try {
            const response = await fetch(`${this.baseUrl}/health`);
            if (!response.ok) return { status: 'error' };
            return await response.json();
        } catch (error) {
            return { status: 'disconnected', error: error.message };
        }
    }
}

const apiService = new BackendService();
let chatHistory = []; // Will be loaded from Service

// DOM Elements
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');
const plusBtn = document.getElementById('plus-btn');
const attachmentMenu = document.getElementById('attachment-menu');
const mainInput = document.getElementById('main-input');
const sendBtn = document.getElementById('send-btn');
const chatContainer = document.getElementById('chat-container');
const welcomeView = document.getElementById('welcome-view');
const recentChatsContainer = document.getElementById('recent-chats');
const newChatBtn = document.querySelector('aside button');
const modelSelectorBtn = document.getElementById('model-selector-btn');
const modelDropdown = document.getElementById('model-dropdown');
const currentModelSpan = document.getElementById('current-model');
const suggestionsGrid = document.getElementById('suggestions-grid');
const infoPanel = document.getElementById('info-panel');
const greetingText = document.getElementById('greeting-text');

// Default Suggestions
const defaultPrompts = [
    { title: "Help me plan a", desc: "database migration strategy" },
    { title: "What are the pros and cons of", desc: "PostgreSQL vs MongoDB" },
    { title: "Write a technical design", desc: "document for an API" },
    { title: "Explain microservices", desc: "architecture patterns" }
];

// Initialize
async function init() {
    chatHistory = await apiService.loadHistory();
    renderRecentChats();
    renderSuggestions();
    updateGreeting();

    // Sidebar Toggle
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('closed');
    });

    // Plus Button Toggle
    plusBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        attachmentMenu.classList.toggle('active');
    });

    // Model Selector Toggle
    modelSelectorBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        modelDropdown.classList.toggle('active');
    });

    // Close menus on outside click
    document.addEventListener('click', () => {
        attachmentMenu.classList.remove('active');
        modelDropdown?.classList.remove('active');
    });

    // Send Button Click
    sendBtn.addEventListener('click', sendMessage);

    // Enter Key Press
    mainInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });

    // New Chat Button
    newChatBtn.addEventListener('click', createNewChat);
}

// Sidebar Render
function renderRecentChats() {
    recentChatsContainer.innerHTML = '';
    chatHistory.slice().reverse().forEach(chat => {
        const div = document.createElement('div');
        div.className = 'group flex items-center gap-3 px-3 py-2 rounded-md hover:bg-white/5 cursor-pointer transition text-slate-400 hover:text-white chat-item-container';
        div.innerHTML = `
            <div class="flex items-center gap-3 truncate flex-1" onclick="loadChat(${chat.id})">
                <i class="fa-regular fa-message text-xs"></i>
                <span class="text-sm truncate">${chat.title}</span>
            </div>
            <button class="delete-chat-btn p-1 hover:bg-white/10 rounded" onclick="event.stopPropagation(); deleteChat(${chat.id})">
                <i class="fa-solid fa-trash text-[10px]"></i>
            </button>
        `;
        recentChatsContainer.appendChild(div);
    });
}

// Suggestions Render
function renderSuggestions() {
    if (!suggestionsGrid) return;
    suggestionsGrid.innerHTML = '';

    // Get unique user prompts from history
    let prompts = [];
    chatHistory.forEach(chat => {
        chat.messages.forEach(msg => {
            if (msg.role === 'user' && !prompts.includes(msg.content)) {
                prompts.push(msg.content);
            }
        });
    });

    // Reversely get the last 4
    prompts = prompts.reverse().slice(0, 4);

    if (prompts.length === 0) {
        // Render defaults if empty
        defaultPrompts.forEach(p => {
            addSuggestionCard(p.title + " " + p.desc, p.title, p.desc);
        });
    } else {
        prompts.forEach(text => {
            const truncated = text.length > 30 ? text.substring(0, 30) + "..." : text;
            addSuggestionCard(text, truncated, "");
        });
    }
}

function addSuggestionCard(fullText, title, subtitle) {
    const div = document.createElement('div');
    div.className = 'glass-card p-5 rounded-xl cursor-pointer group';
    div.onclick = () => fillInput(fullText);
    div.innerHTML = `
        <h3 class="text-white font-medium mb-1 group-hover:text-indigo-300 transition">${title}</h3>
        <p class="text-slate-500 text-sm">${subtitle}</p>
    `;
    suggestionsGrid.appendChild(div);
}

// Chat Actions
function createNewChat() {
    currentChatId = null;

    // Show welcome view
    welcomeView.classList.remove('hidden');

    // Remove any existing chat messages
    const existingChatView = document.querySelector('.chat-messages-container');
    if (existingChatView) existingChatView.remove();

    // Clear input and refresh suggestions
    mainInput.value = '';
    mainInput.focus();
    renderSuggestions();
}

async function sendMessage() {
    const text = mainInput.value.trim();
    if (!text) return;

    if (!currentChatId) {
        currentChatId = Date.now();
        welcomeView.classList.add('hidden');

        const messagesDiv = document.createElement('div');
        messagesDiv.className = 'chat-messages-container';
        chatContainer.prepend(messagesDiv);

        chatHistory.push({
            id: currentChatId,
            title: text.length > 25 ? text.substring(0, 25) + '...' : text,
            messages: []
        });
    }

    const messagesDiv = document.querySelector('.chat-messages-container');
    addMessage(messagesDiv, text, 'user');
    mainInput.value = '';

    // Show and run process details only for Thinking model when message is sent
    if (selectedModel === 'Thinking') {
        infoPanel?.classList.remove('hidden');
        runProcessAnimation();
    }

    // Add thinking indicator
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'chat-message ai-message thinking-indicator';
    thinkingDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Thinking...';
    messagesDiv.appendChild(thinkingDiv);

    try {
        // Call backend API for AI response (Nova LLM)
        const response = await apiService.sendMessage(text, selectedModel, attachedFiles, currentChatId);

        // Remove thinking indicator
        thinkingDiv.remove();

        // Add AI response
        const aiContent = response.content || "I couldn't generate a response.";
        addMessage(messagesDiv, aiContent, 'ai');

        // Save to chat history
        const chat = chatHistory.find(c => c.id === currentChatId);
        if (chat) {
            chat.messages.push({ role: 'user', content: text });
            chat.messages.push({ role: 'ai', content: aiContent });
            await saveHistory();
            renderRecentChats();
        }

        // Clear attachments after sending
        attachedFiles = [];
        const attachmentDisplay = document.getElementById('attachment-display');
        if (attachmentDisplay) attachmentDisplay.remove();

    } catch (error) {
        console.error('Error in sendMessage:', error);
        thinkingDiv.remove();
        addMessage(messagesDiv, 'Sorry, an error occurred. Please try again.', 'ai');
    }
}

function addMessage(container, text, type) {
    const div = document.createElement('div');
    div.className = `chat-message ${type}-message`;
    div.textContent = text;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// Helper function to save chat history
async function saveHistory() {
    await apiService.saveHistory(chatHistory);
}

function loadChat(id) {
    const chat = chatHistory.find(c => c.id === id);
    if (!chat) return;

    currentChatId = id;
    welcomeView.classList.add('hidden');
    infoPanel.classList.add('hidden'); // Reset info panel on load

    let messagesDiv = document.querySelector('.chat-messages-container');
    if (!messagesDiv) {
        messagesDiv = document.createElement('div');
        messagesDiv.className = 'chat-messages-container';
        chatContainer.prepend(messagesDiv);
    } else {
        messagesDiv.innerHTML = '';
    }

    chat.messages.forEach(msg => {
        addMessage(messagesDiv, msg.content, msg.role === 'user' ? 'user' : 'ai');
    });
}

async function deleteChat(id) {
    if (confirm('Are you sure you want to delete this chat?')) {
        await apiService.deleteChat(id); // Backend call

        chatHistory = chatHistory.filter(c => c.id !== id);
        if (currentChatId === id) {
            createNewChat();
        }
        await apiService.saveHistory(chatHistory);
        renderRecentChats();
        renderSuggestions();
    }
}

function selectModel(model) {
    selectedModel = model;
    currentModelSpan.textContent = model;
    document.querySelectorAll('.model-check').forEach(el => el.classList.add('hidden'));
    document.getElementById(`check-${model}`).classList.remove('hidden');
    modelDropdown.classList.remove('active');

    // Panel remains hidden on selection; it only shows on message send
}

// Node Configuration
const nodeConfig = {
    thinking: { icon: 'fa-brain', color: 'text-indigo-400', label: 'Thinking' },
    processing: { icon: 'fa-microchip', color: 'text-blue-400', label: 'Processing' },
    analyzing: { icon: 'fa-magnifying-glass-chart', color: 'text-purple-400', label: 'Analyzing' },
    fixing: { icon: 'fa-wrench', color: 'text-emerald-400', label: 'Fixing' },
    plan: { icon: 'fa-list-check', color: 'text-amber-400', label: 'Implementation Plan' },
    walkthrough: { icon: 'fa-person-walking', color: 'text-rose-400', label: 'Walkthrough' }
};

const hierarchyTree = document.getElementById('hierarchy-tree');

// Clear all nodes
function clearProcessNodes() {
    if (hierarchyTree) hierarchyTree.innerHTML = '';
}

// Add a single node dynamically
function addProcessNode(nodeKey, content) {
    const config = nodeConfig[nodeKey];
    if (!config || !hierarchyTree) return;

    const nodeId = `node-${nodeKey}`;

    // Check if node already exists
    let existing = document.getElementById(nodeId);
    if (existing) {
        existing.textContent = content;
        return;
    }

    const nodeDiv = document.createElement('div');
    nodeDiv.className = 'tree-node group active';
    nodeDiv.onclick = () => toggleNode(nodeId);
    nodeDiv.innerHTML = `
        <div class="flex items-center gap-3 ${config.color} cursor-pointer">
            <i class="fa-solid ${config.icon} text-sm"></i>
            <span class="text-sm font-medium">${config.label}</span>
            <i class="fa-solid fa-chevron-down text-[10px] ml-auto transition-transform node-chevron"></i>
        </div>
        <div id="${nodeId}" class="node-content mt-2 ml-7 text-xs text-slate-400 pl-3 border-l border-white/10">
            ${content}
        </div>
    `;
    hierarchyTree.appendChild(nodeDiv);
}

// Toggle node visibility
function toggleNode(id) {
    const content = document.getElementById(id);
    if (!content) return;
    const node = content.parentElement;

    if (content.classList.contains('hidden')) {
        content.classList.remove('hidden');
        node.classList.add('active');
    } else {
        content.classList.add('hidden');
        node.classList.remove('active');
    }
}

// Simulate AI process with mock content
function runProcessAnimation() {
    clearProcessNodes();

    const mockSteps = [
        { key: 'thinking', content: 'Parsing user intent and initializing context...' },
        { key: 'processing', content: 'Structuring data and setting up parameters...' },
        { key: 'analyzing', content: 'Evaluating patterns and checking edge cases...' },
        { key: 'fixing', content: 'Applying corrections and optimizations...' },
        { key: 'plan', content: 'Generating step-by-step implementation roadmap...' },
        { key: 'walkthrough', content: 'Compiling final summary and validation steps...' }
    ];

    let i = 0;
    const interval = setInterval(() => {
        if (i >= mockSteps.length) {
            clearInterval(interval);
            return;
        }
        addProcessNode(mockSteps[i].key, mockSteps[i].content);
        i++;
    }, 500);
}

// Old saveHistory removed. Using apiService.saveHistory()

// File Upload State
let attachedFiles = [];

// File Input Elements
const docInput = document.getElementById('doc-input');
const imageInput = document.getElementById('image-input');
const codeInput = document.getElementById('code-input');

// Handle Attachment Selection
function handleAttachment(type) {
    attachmentMenu.classList.remove('active');

    switch (type) {
        case 'doc':
            docInput.click();
            break;
        case 'image':
            imageInput.click();
            break;
        case 'code':
            codeInput.click();
            break;
    }
}

// File Upload Handlers
if (docInput) {
    docInput.addEventListener('change', (e) => handleFileUpload(e, 'document'));
}
if (imageInput) {
    imageInput.addEventListener('change', (e) => handleFileUpload(e, 'image'));
}
if (codeInput) {
    codeInput.addEventListener('change', (e) => handleFileUpload(e, 'code'));
}

async function handleFileUpload(event, type) {
    const file = event.target.files[0];
    if (!file) return;

    // Call Backend API to upload/index file (LanceDB/KuzuDB)
    await apiService.uploadFile(file);

    const fileData = {
        name: file.name,
        size: formatFileSize(file.size),
        type: type,
        file: file
    };

    attachedFiles.push(fileData);
    displayAttachedFile(fileData);

    // Reset input
    event.target.value = '';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function displayAttachedFile(fileData) {
    const container = document.querySelector('.input-wrapper');
    let attachmentDisplay = document.getElementById('attachment-display');

    if (!attachmentDisplay) {
        attachmentDisplay = document.createElement('div');
        attachmentDisplay.id = 'attachment-display';
        attachmentDisplay.className = 'flex flex-wrap gap-2 mb-2';
        container.insertBefore(attachmentDisplay, container.firstChild);
    }

    const fileChip = document.createElement('div');
    fileChip.className = 'glass-card px-3 py-2 rounded-lg flex items-center gap-2 text-xs';

    const icon = getFileIcon(fileData.type);
    fileChip.innerHTML = `
        <i class="${icon}"></i>
        <span class="text-white">${fileData.name}</span>
        <span class="text-slate-500">${fileData.size}</span>
        <button onclick="removeAttachment('${fileData.name}')" class="ml-2 text-slate-400 hover:text-red-400">
            <i class="fa-solid fa-xmark"></i>
        </button>
    `;

    attachmentDisplay.appendChild(fileChip);
}

function getFileIcon(type) {
    switch (type) {
        case 'document':
            return 'fa-solid fa-file-lines text-blue-400';
        case 'image':
            return 'fa-solid fa-image text-emerald-400';
        case 'code':
            return 'fa-solid fa-code text-purple-400';
        default:
            return 'fa-solid fa-file text-slate-400';
    }
}

function removeAttachment(fileName) {
    attachedFiles = attachedFiles.filter(f => f.name !== fileName);

    const attachmentDisplay = document.getElementById('attachment-display');
    if (attachmentDisplay) {
        const chips = attachmentDisplay.querySelectorAll('.glass-card');
        chips.forEach(chip => {
            if (chip.textContent.includes(fileName)) {
                chip.remove();
            }
        });

        if (attachedFiles.length === 0) {
            attachmentDisplay.remove();
        }
    }
}

// Expose to window for onclick handlers
window.removeAttachment = removeAttachment;
window.handleAttachment = handleAttachment;
window.selectModel = selectModel;
window.loadChat = loadChat;
window.deleteChat = deleteChat;

function fillInput(text) {
    mainInput.value = "";
    mainInput.focus();
    let i = 0;
    if (window.typeInterval) clearInterval(window.typeInterval);
    window.typeInterval = setInterval(() => {
        mainInput.value += text.charAt(i);
        i++;
        if (i >= text.length) clearInterval(window.typeInterval);
    }, 15);
}

// Update greeting based on time of day
function updateGreeting() {
    const greetingText = document.getElementById('greeting-text');
    if (!greetingText) return;

    const hour = new Date().getHours();
    let greeting;

    if (hour < 12) {
        greeting = 'Good morning';
    } else if (hour < 17) {
        greeting = 'Good afternoon';
    } else {
        greeting = 'Good evening';
    }

    greetingText.textContent = `${greeting}, there`;
}

init();
window.toggleNode = toggleNode; // Expose to HTML