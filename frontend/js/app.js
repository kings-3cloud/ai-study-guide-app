'use strict';

// ---------------------------------------------------------------------------
// Thread helpers
// ---------------------------------------------------------------------------

const SESSION_KEY = 'study_thread_id';

async function createThread() {
  const res = await fetch('/api/thread', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  const data = await res.json();
  return data.thread_id;
}

async function ensureThread() {
  let threadId = sessionStorage.getItem(SESSION_KEY);
  if (!threadId) {
    threadId = await createThread();
    sessionStorage.setItem(SESSION_KEY, threadId);
  }
  return threadId;
}

// ---------------------------------------------------------------------------
// Message rendering
// ---------------------------------------------------------------------------

function appendMessage(chatBox, role, text, loading = false) {
  const wrapper = document.createElement('div');
  wrapper.classList.add('message', role);

  const label = document.createElement('div');
  label.classList.add('message-label');
  label.textContent = role === 'user' ? 'You' : 'Study Assistant';

  const bubble = document.createElement('div');
  bubble.classList.add('message-bubble');
  if (loading) bubble.classList.add('loading');
  bubble.textContent = text;

  wrapper.appendChild(label);
  wrapper.appendChild(bubble);
  chatBox.appendChild(wrapper);
  chatBox.scrollTop = chatBox.scrollHeight;

  return bubble; // caller can mutate text/class later
}

// ---------------------------------------------------------------------------
// Send message
// ---------------------------------------------------------------------------

async function sendMessage({ chatBox, input, sendBtn }) {
  const text = input.value.trim();
  if (!text) return;

  const threadId = sessionStorage.getItem(SESSION_KEY);
  if (!threadId) return;

  input.value = '';
  sendBtn.disabled = true;

  appendMessage(chatBox, 'user', text);
  const loadingBubble = appendMessage(chatBox, 'assistant', 'Thinking…', true);

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ thread_id: threadId, message: text, user_id: 'default_user' }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      loadingBubble.textContent = `Error: ${err.detail || 'Something went wrong.'}`;
    } else {
      const data = await res.json();
      loadingBubble.textContent = data.response;
    }
  } catch (err) {
    loadingBubble.textContent = `Network error: ${err.message}`;
  } finally {
    loadingBubble.classList.remove('loading');
    sendBtn.disabled = false;
    input.focus();
  }
}

// ---------------------------------------------------------------------------
// File upload
// ---------------------------------------------------------------------------

async function uploadPDF(file, input) {
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload-pdf', { method: 'POST', body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      alert(`Upload failed: ${err.detail || 'Unknown error.'}`);
      return;
    }
    const data = await res.json();
    input.value = `Study this PDF: ${data.file_path}`;
    input.focus();
  } catch (err) {
    alert(`Upload error: ${err.message}`);
  }
}

// ---------------------------------------------------------------------------
// New Chat
// ---------------------------------------------------------------------------

async function startNewChat(chatBox, input) {
  try {
    const threadId = await createThread();
    sessionStorage.setItem(SESSION_KEY, threadId);
    chatBox.innerHTML = '';
    input.value = '';
    input.focus();
  } catch (err) {
    console.error('Failed to create new thread:', err);
  }
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  const chatBox  = document.getElementById('chat-box');
  const input    = document.getElementById('message-input');
  const sendBtn  = document.getElementById('send-btn');
  const newChatBtn = document.getElementById('new-chat-btn');
  const uploadBtn  = document.getElementById('upload-btn');
  const pdfInput   = document.getElementById('pdf-input');

  // Create thread on first load
  try {
    await ensureThread();
  } catch (err) {
    console.error('Thread init failed:', err);
    appendMessage(chatBox, 'assistant', 'Could not connect to the server. Please refresh.');
    return;
  }

  // Send on button click
  sendBtn.addEventListener('click', () => sendMessage({ chatBox, input, sendBtn }));

  // Send on Enter (Shift+Enter inserts newline if input were a textarea)
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage({ chatBox, input, sendBtn });
    }
  });

  // File upload: trigger hidden input
  uploadBtn.addEventListener('click', () => pdfInput.click());

  pdfInput.addEventListener('change', async () => {
    const file = pdfInput.files[0];
    if (file) {
      await uploadPDF(file, input);
      pdfInput.value = ''; // reset so the same file can be re-selected
    }
  });

  // New chat
  newChatBtn.addEventListener('click', () => startNewChat(chatBox, input));
});
