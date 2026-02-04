/**
 * Nytro AI Interview Chatbot - Frontend JavaScript
 */

class InterviewChatbot {
    constructor() {
        // DOM Elements
        this.welcomeScreen = document.getElementById('welcomeScreen');
        this.chatMessages = document.getElementById('chatMessages');
        this.completionScreen = document.getElementById('completionScreen');
        this.completionMessage = document.getElementById('completionMessage');
        this.inputContainer = document.getElementById('inputContainer');
        this.phaseContainer = document.getElementById('phaseContainer');
        this.responseForm = document.getElementById('responseForm');
        this.responseInput = document.getElementById('responseInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.startBtn = document.getElementById('startBtn');

        // State
        this.isProcessing = false;
        this.sessionId = null;
        this.currentPhase = null;

        // Bind events
        this.bindEvents();
    }

    bindEvents() {
        // Start button
        this.startBtn.addEventListener('click', () => this.startInterview());

        // Form submission
        this.responseForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitResponse();
        });

        // Auto-resize textarea
        this.responseInput.addEventListener('input', () => {
            this.autoResizeTextarea();
        });

        // Keyboard shortcuts
        this.responseInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.submitResponse();
            }
        });
    }

    autoResizeTextarea() {
        this.responseInput.style.height = 'auto';
        this.responseInput.style.height = Math.min(this.responseInput.scrollHeight, 150) + 'px';
    }

    updatePhase(phase) {
        if (phase === this.currentPhase) return;
        this.currentPhase = phase;

        // Update phase indicators
        document.querySelectorAll('.phase-item').forEach(item => {
            const itemPhase = item.dataset.phase;
            item.classList.remove('active', 'completed');
            
            const phaseOrder = ['introduction', 'collect_info', 'skills_assessment', 'closing'];
            const currentIndex = phaseOrder.indexOf(phase);
            const itemIndex = phaseOrder.indexOf(itemPhase);
            
            if (itemIndex < currentIndex) {
                item.classList.add('completed');
            } else if (itemIndex === currentIndex) {
                item.classList.add('active');
            }
        });
    }

    async startInterview() {
        try {
            this.startBtn.disabled = true;
            this.startBtn.textContent = 'Starting...';

            const response = await fetch('/api/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (data.success) {
                this.sessionId = data.session_id;
                
                // Hide welcome, show chat
                this.welcomeScreen.style.display = 'none';
                this.chatMessages.style.display = 'flex';
                this.inputContainer.style.display = 'block';
                this.phaseContainer.style.display = 'block';

                // Update phase
                this.updatePhase(data.phase);

                // Show first message
                this.addBotMessage(data.message);

                // Focus input
                this.responseInput.focus();
            } else {
                this.showError(data.error || 'Failed to start interview');
                this.startBtn.disabled = false;
                this.startBtn.textContent = 'Start Interview';
            }
        } catch (error) {
            console.error('Error starting interview:', error);
            this.showError('Failed to connect to server. Please refresh and try again.');
            this.startBtn.disabled = false;
            this.startBtn.textContent = 'Start Interview';
        }
    }

    async submitResponse() {
        const response = this.responseInput.value.trim();

        if (!response || this.isProcessing) return;

        this.isProcessing = true;
        this.sendBtn.disabled = true;

        // Add user message
        this.addUserMessage(response);

        // Clear input
        this.responseInput.value = '';
        this.responseInput.style.height = 'auto';

        // Show typing indicator
        const typingId = this.showTypingIndicator();

        try {
            const apiResponse = await fetch('/api/respond', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ response })
            });

            const data = await apiResponse.json();

            // Remove typing indicator
            this.removeTypingIndicator(typingId);

            if (data.success) {
                // Update phase
                if (data.phase) {
                    this.updatePhase(data.phase);
                }

                if (data.complete) {
                    // Add final message
                    this.addBotMessage(data.message);
                    
                    // Show completion after a delay
                    setTimeout(() => {
                        this.showCompletion(data);
                    }, 2000);
                } else {
                    // Show next message
                    this.addBotMessage(data.message);
                    this.responseInput.focus();
                }
            } else {
                this.addBotMessage(data.error || 'Something went wrong. Please try again.');
            }
        } catch (error) {
            console.error('Error submitting response:', error);
            this.removeTypingIndicator(typingId);
            this.addBotMessage('Network error. Please check your connection and try again.');
        }

        this.isProcessing = false;
        this.sendBtn.disabled = false;
    }

    addBotMessage(text) {
        const message = document.createElement('div');
        message.className = 'message bot';
        message.innerHTML = `
            <div class="message-avatar">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M12 16v-4"/>
                    <path d="M12 8h.01"/>
                </svg>
            </div>
            <div class="message-bubble">${this.formatMessage(text)}</div>
        `;
        this.chatMessages.appendChild(message);
        this.scrollToBottom();
    }

    addUserMessage(text) {
        const message = document.createElement('div');
        message.className = 'message user';
        message.innerHTML = `
            <div class="message-avatar">You</div>
            <div class="message-bubble">${this.escapeHtml(text)}</div>
        `;
        this.chatMessages.appendChild(message);
        this.scrollToBottom();
    }

    formatMessage(text) {
        // Escape HTML first
        let formatted = this.escapeHtml(text);
        // Convert newlines to breaks
        formatted = formatted.replace(/\n/g, '<br>');
        return formatted;
    }

    showTypingIndicator() {
        const id = 'typing-' + Date.now();
        const typing = document.createElement('div');
        typing.className = 'message bot';
        typing.id = id;
        typing.innerHTML = `
            <div class="message-avatar">
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M12 16v-4"/>
                    <path d="M12 8h.01"/>
                </svg>
            </div>
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        this.chatMessages.appendChild(typing);
        this.scrollToBottom();
        return id;
    }

    removeTypingIndicator(id) {
        const typing = document.getElementById(id);
        if (typing) {
            typing.remove();
        }
    }

    showCompletion(data) {
        this.chatMessages.style.display = 'none';
        this.inputContainer.style.display = 'none';
        this.phaseContainer.style.display = 'none';
        this.completionScreen.style.display = 'flex';
        
        let message = "Thank you for completing your interview! Our team will review your responses.";
        
        if (data.evaluation_summary) {
            message = `Your interview has been completed and evaluated. Our team will review the results and be in touch within 5-7 business days.`;
        }
        
        this.completionMessage.textContent = message;
    }

    showError(message) {
        // Create a toast notification
        const toast = document.createElement('div');
        toast.className = 'error-toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('show');
        }, 100);
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.interviewBot = new InterviewChatbot();
});
