/**
 * Nytro AI Interview Chatbot - Frontend JavaScript
 * Enhanced with progress tracking, pause/resume, timeout handling, and feedback
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
        this.consentCheckbox = document.getElementById('consentCheckbox');
        
        // Progress elements
        this.progressBar = document.getElementById('progressBar');
        this.progressText = document.getElementById('progressText');
        this.timeRemaining = document.getElementById('timeRemaining');
        
        // Session controls
        this.sessionControls = document.getElementById('sessionControls');
        this.pauseBtn = document.getElementById('pauseBtn');
        this.pauseModal = document.getElementById('pauseModal');
        this.resumeBtn = document.getElementById('resumeBtn');
        this.timeoutModal = document.getElementById('timeoutModal');
        this.continueBtn = document.getElementById('continueBtn');
        
        // Feedback elements
        this.feedbackSection = document.getElementById('feedbackSection');
        this.feedbackComment = document.getElementById('feedbackComment');
        this.feedbackThanks = document.getElementById('feedbackThanks');
        this.feedbackText = document.getElementById('feedbackText');
        this.submitFeedbackBtn = document.getElementById('submitFeedback');

        // State
        this.isProcessing = false;
        this.sessionId = null;
        this.currentPhase = null;
        this.isPaused = false;
        this.questionCount = 0;
        this.maxQuestions = 12; // Approximate
        this.startTime = null;
        this.selectedFeedback = null;
        this.candidateEmail = null; // Track candidate email for confirmation
        
        // Timers
        this.inactivityTimer = null;
        this.inactivityWarningTimer = null;
        this.INACTIVITY_WARNING_MS = 5 * 60 * 1000; // 5 min warning
        this.INACTIVITY_TIMEOUT_MS = 2 * 60 * 1000; // 2 min after warning
        this.pauseTimeoutTimer = null;
        this.PAUSE_TIMEOUT_MS = 30 * 60 * 1000; // 30 min pause limit

        // Bind events
        this.bindEvents();
        
        // Track page view
        this.trackAnalytics('page_view', { page: 'interview' });
    }

    bindEvents() {
        // Consent checkbox
        if (this.consentCheckbox) {
            this.consentCheckbox.addEventListener('change', () => {
                this.startBtn.disabled = !this.consentCheckbox.checked;
            });
        }
        
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
            this.resetInactivityTimer();
        });

        // Keyboard shortcuts
        this.responseInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.submitResponse();
            }
        });
        
        // Pause/Resume
        if (this.pauseBtn) {
            this.pauseBtn.addEventListener('click', () => this.pauseInterview());
        }
        if (this.resumeBtn) {
            this.resumeBtn.addEventListener('click', () => this.resumeInterview());
        }
        if (this.continueBtn) {
            this.continueBtn.addEventListener('click', () => this.dismissTimeoutWarning());
        }
        
        // Feedback buttons
        document.querySelectorAll('.feedback-btn').forEach(btn => {
            btn.addEventListener('click', () => this.selectFeedback(btn));
        });
        if (this.submitFeedbackBtn) {
            this.submitFeedbackBtn.addEventListener('click', () => this.submitFeedback());
        }
        
        // Track page unload (drop-off)
        window.addEventListener('beforeunload', () => {
            if (this.sessionId && this.currentPhase !== 'complete') {
                this.trackAnalytics('drop_off', {
                    phase: this.currentPhase,
                    question_count: this.questionCount,
                    time_spent: this.getTimeSpent()
                });
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
    
    updateProgress() {
        this.questionCount++;
        
        // Update progress bar
        const progress = Math.min((this.questionCount / this.maxQuestions) * 100, 95);
        if (this.progressBar) {
            this.progressBar.style.width = progress + '%';
        }
        
        // Update progress text
        if (this.progressText) {
            if (this.currentPhase === 'collect_info') {
                this.progressText.textContent = 'Getting your info...';
            } else if (this.currentPhase === 'skills_assessment') {
                this.progressText.textContent = `Question ${Math.min(this.questionCount - 2, this.maxQuestions - 2)} of ~${this.maxQuestions - 2}`;
            } else if (this.currentPhase === 'closing') {
                this.progressText.textContent = 'Wrapping up...';
            } else {
                this.progressText.textContent = 'Starting...';
            }
        }
        
        // Update time remaining
        if (this.timeRemaining && this.startTime) {
            const elapsed = Math.floor((Date.now() - this.startTime) / 1000 / 60);
            const remaining = Math.max(10 - elapsed, 1);
            this.timeRemaining.textContent = `~${remaining} min remaining`;
        }
    }

    async startInterview() {
        try {
            this.startBtn.disabled = true;
            this.startBtn.textContent = 'Starting...';
            
            this.trackAnalytics('interview_start', { consent_given: true });

            const response = await fetch('/api/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();

            if (data.success) {
                this.sessionId = data.session_id;
                this.startTime = Date.now();
                
                // Hide welcome, show chat
                this.welcomeScreen.style.display = 'none';
                this.chatMessages.style.display = 'flex';
                this.inputContainer.style.display = 'block';
                this.phaseContainer.style.display = 'block';
                if (this.sessionControls) {
                    this.sessionControls.style.display = 'flex';
                }

                // Update phase
                this.updatePhase(data.phase);

                // Show first message
                this.addBotMessage(data.message);

                // Focus input
                this.responseInput.focus();
                
                // Start inactivity timer
                this.startInactivityTimer();
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

        if (!response || this.isProcessing || this.isPaused) return;

        this.isProcessing = true;
        this.sendBtn.disabled = true;
        this.resetInactivityTimer();

        // Add user message
        this.addUserMessage(response);
        
        // Capture email if it looks like one (for confirmation display)
        if (response.includes('@') && response.includes('.')) {
            const emailMatch = response.match(/[\w.-]+@[\w.-]+\.\w+/);
            if (emailMatch) {
                this.candidateEmail = emailMatch[0];
            }
        }

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
                
                // Update progress
                this.updateProgress();

                if (data.complete) {
                    // Track completion
                    this.trackAnalytics('interview_complete', {
                        question_count: this.questionCount,
                        time_spent: this.getTimeSpent(),
                        recommendation: data.evaluation_summary?.recommendation
                    });
                    
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
    
    // Pause/Resume functionality
    pauseInterview() {
        this.isPaused = true;
        this.clearInactivityTimer();
        
        if (this.pauseModal) {
            this.pauseModal.style.display = 'flex';
        }
        
        // Start pause timeout countdown
        this.startPauseTimeout();
        
        this.trackAnalytics('interview_paused', {
            phase: this.currentPhase,
            question_count: this.questionCount
        });
    }
    
    resumeInterview() {
        this.isPaused = false;
        
        if (this.pauseModal) {
            this.pauseModal.style.display = 'none';
        }
        
        // Clear pause timeout
        if (this.pauseTimeoutTimer) {
            clearInterval(this.pauseTimeoutTimer);
        }
        
        // Restart inactivity timer
        this.startInactivityTimer();
        
        // Focus input
        this.responseInput.focus();
        
        this.trackAnalytics('interview_resumed', {
            phase: this.currentPhase
        });
    }
    
    startPauseTimeout() {
        let remaining = this.PAUSE_TIMEOUT_MS / 1000;
        const countdown = document.getElementById('timeoutCountdown');
        
        this.pauseTimeoutTimer = setInterval(() => {
            remaining--;
            if (countdown) {
                const mins = Math.floor(remaining / 60);
                const secs = remaining % 60;
                countdown.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
            }
            
            if (remaining <= 0) {
                clearInterval(this.pauseTimeoutTimer);
                this.handleSessionExpired();
            }
        }, 1000);
    }
    
    // Inactivity handling
    startInactivityTimer() {
        this.clearInactivityTimer();
        
        this.inactivityTimer = setTimeout(() => {
            this.showInactivityWarning();
        }, this.INACTIVITY_WARNING_MS);
    }
    
    resetInactivityTimer() {
        if (!this.isPaused && this.sessionId) {
            this.startInactivityTimer();
        }
    }
    
    clearInactivityTimer() {
        if (this.inactivityTimer) {
            clearTimeout(this.inactivityTimer);
        }
        if (this.inactivityWarningTimer) {
            clearInterval(this.inactivityWarningTimer);
        }
    }
    
    showInactivityWarning() {
        if (this.timeoutModal) {
            this.timeoutModal.style.display = 'flex';
        }
        
        let remaining = this.INACTIVITY_TIMEOUT_MS / 1000;
        const countdown = document.getElementById('inactivityCountdown');
        
        this.inactivityWarningTimer = setInterval(() => {
            remaining--;
            if (countdown) {
                const mins = Math.floor(remaining / 60);
                const secs = remaining % 60;
                countdown.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
            }
            
            if (remaining <= 0) {
                clearInterval(this.inactivityWarningTimer);
                this.handleSessionExpired();
            }
        }, 1000);
    }
    
    dismissTimeoutWarning() {
        if (this.timeoutModal) {
            this.timeoutModal.style.display = 'none';
        }
        if (this.inactivityWarningTimer) {
            clearInterval(this.inactivityWarningTimer);
        }
        this.startInactivityTimer();
        this.responseInput.focus();
    }
    
    handleSessionExpired() {
        this.trackAnalytics('session_expired', {
            phase: this.currentPhase,
            question_count: this.questionCount,
            was_paused: this.isPaused
        });
        
        // Redirect to start
        window.location.reload();
    }
    
    // Feedback functionality
    selectFeedback(btn) {
        // Remove selected from all
        document.querySelectorAll('.feedback-btn').forEach(b => b.classList.remove('selected'));
        
        // Add selected to clicked
        btn.classList.add('selected');
        this.selectedFeedback = btn.dataset.rating;
        
        // Show comment box
        if (this.feedbackComment) {
            this.feedbackComment.style.display = 'block';
        }
    }
    
    async submitFeedback() {
        if (!this.selectedFeedback) return;
        
        const comment = this.feedbackText ? this.feedbackText.value.trim() : '';
        
        this.trackAnalytics('feedback_submitted', {
            rating: this.selectedFeedback,
            has_comment: !!comment,
            session_id: this.sessionId
        });
        
        // Send to server
        try {
            await fetch('/api/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    rating: this.selectedFeedback,
                    comment: comment
                })
            });
        } catch (e) {
            console.error('Failed to submit feedback:', e);
        }
        
        // Show thanks
        if (this.feedbackSection) {
            this.feedbackSection.innerHTML = '<div class="feedback-thanks"><p>Thanks for your feedback!</p></div>';
        }
    }
    
    // Analytics tracking
    trackAnalytics(event, data = {}) {
        // Add common data
        const payload = {
            event,
            timestamp: new Date().toISOString(),
            session_id: this.sessionId,
            ...data
        };
        
        // Send to server (fire and forget)
        try {
            navigator.sendBeacon('/api/analytics', JSON.stringify(payload));
        } catch (e) {
            // Fallback to fetch
            fetch('/api/analytics', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                keepalive: true
            }).catch(() => {});
        }
        
        // Also log to console in dev
        console.log('[Analytics]', event, data);
    }
    
    getTimeSpent() {
        if (!this.startTime) return 0;
        return Math.floor((Date.now() - this.startTime) / 1000);
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
        if (this.sessionControls) {
            this.sessionControls.style.display = 'none';
        }
        this.completionScreen.style.display = 'flex';
        
        // Clear timers
        this.clearInactivityTimer();
        
        // Complete progress bar
        if (this.progressBar) {
            this.progressBar.style.width = '100%';
        }
        
        let message = "Thank you for completing your interview! Our team will review your responses.";
        
        if (data.evaluation_summary) {
            message = `Your interview has been completed and evaluated. Our team will review the results and be in touch within 5-7 business days.`;
        }
        
        this.completionMessage.textContent = message;
        
        // Show email confirmation
        const emailConfirmation = document.getElementById('emailConfirmation');
        const confirmationEmail = document.getElementById('confirmationEmail');
        
        if (this.candidateEmail && emailConfirmation && confirmationEmail) {
            confirmationEmail.textContent = this.candidateEmail;
            emailConfirmation.style.display = 'flex';
        } else if (emailConfirmation) {
            // Hide if no email captured
            emailConfirmation.style.display = 'none';
        }
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
        // Use setTimeout to ensure DOM is fully updated before scrolling
        setTimeout(() => {
            // Scroll the chat messages container
            if (this.chatMessages) {
                this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
            }
            
            // Also scroll the parent chat container
            const chatContainer = document.getElementById('chatContainer');
            if (chatContainer) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
            
            // Also scroll the last message into view as final backup
            const lastMessage = this.chatMessages?.lastElementChild;
            if (lastMessage) {
                lastMessage.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }
        }, 50);
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
