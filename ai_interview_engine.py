"""
AI Interview Engine
Powered by OpenAI for intelligent, adaptive candidate interviews.
"""

import os
import re
import json
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from openai import OpenAI

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class SkillScore:
    """Score for a single skill"""
    skill_id: str
    skill_name: str
    score: int  # 1-5
    confidence: float  # 0-1, how confident the AI is in this score
    evidence: List[str]  # Quotes or observations supporting the score
    concerns: List[str]  # Any red flags observed
    follow_up_needed: bool
    follow_up_questions: List[str]


@dataclass
class CandidateEvaluation:
    """Complete evaluation of a candidate"""
    candidate_name: str
    candidate_email: str
    interview_date: str
    role: str
    
    # Scores
    skill_scores: Dict[str, SkillScore]
    weighted_average: float
    
    # Recommendation
    recommendation: str  # strong_yes, yes, maybe, no
    recommendation_label: str
    recommendation_description: str
    
    # Summary
    strengths: List[str]
    concerns: List[str]
    overall_summary: str
    
    # Follow-up
    recommended_for_followup: bool
    followup_focus_areas: List[str]
    followup_questions: List[str]
    
    # Optional (collected during interview)
    candidate_linkedin: str = ""


@dataclass
class ConversationTurn:
    """A single turn in the conversation"""
    role: str  # 'assistant' or 'user'
    content: str
    timestamp: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class InterviewSession:
    """Complete interview session state"""
    session_id: str
    candidate_name: str = ""
    candidate_email: str = ""
    candidate_linkedin: str = ""
    candidate_location: str = ""
    candidate_availability: str = ""
    
    conversation_history: List[ConversationTurn] = field(default_factory=list)
    collected_info: Dict[str, str] = field(default_factory=dict)
    
    skills_discussed: List[str] = field(default_factory=list)
    current_skill: Optional[str] = None
    questions_asked_per_skill: Dict[str, int] = field(default_factory=dict)
    
    phase: str = "introduction"  # introduction, collect_info, skills_assessment, closing, complete
    turn_count: int = 0
    closure_asked_questions: bool = False  # True after AI asked "any questions?"
    last_validation_error: str = ""  # "email" or "linkedin_url" when last response was invalid
    
    started_at: str = ""
    completed_at: Optional[str] = None
    
    # Raw responses for skill evaluation
    skill_responses: Dict[str, List[Dict]] = field(default_factory=dict)


# =============================================================================
# AI INTERVIEW ENGINE
# =============================================================================

class AIInterviewEngine:
    """
    Intelligent interview engine powered by OpenAI.
    
    Features:
    - Dynamic question generation based on candidate responses
    - Adaptive follow-up questions for vague or strong answers
    - Structured evaluation with consistent scoring
    - Conversation memory for context-aware responses
    """
    
    def __init__(self, config_path: str = "interview_guidelines.yaml"):
        """Initialize the engine with configuration"""
        self.config = self._load_config(config_path)
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.sessions: Dict[str, InterviewSession] = {}
        
    def _load_config(self, config_path: str) -> Dict:
        """Load interview configuration from YAML file"""
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _extract_email(self, text: str) -> Optional[str]:
        """Extract and validate email from text. Returns email or None if invalid."""
        text = text.strip()

        # Reject strings with spaces (e.g. "berteloo @ com")
        if ' ' in text:
            return None

        # Reject obviously incomplete: ends with @ or has no domain
        if text.endswith('@') or '@' not in text:
            return None

        # Full validation regex:
        # - Local part: starts with alphanumeric, can contain ._%+-, ends with alphanumeric
        # - No consecutive dots (checked below)
        # - Domain: starts with alphanumeric, can contain .-, TLD is 2+ letters
        email_pattern = r'^[a-zA-Z0-9](?:[a-zA-Z0-9._%+-]*[a-zA-Z0-9])?@[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, text):
            return None

        email = text
        local, domain = email.split('@', 1)

        # Check for consecutive dots in local part
        if '..' in local:
            return None

        # Domain must have a dot and be at least 4 chars (e.g., "a.co")
        if len(domain) < 4 or '.' not in domain:
            return None

        # Validate TLD is reasonable (2-10 chars, letters only)
        tld = domain.rsplit('.', 1)[-1]
        if not tld.isalpha() or len(tld) < 2 or len(tld) > 10:
            return None

        return email
    
    def _extract_linkedin_url(self, text: str) -> Optional[str]:
        """Extract and validate LinkedIn profile URL. Returns URL or None if invalid."""
        text = text.strip()

        # Reject malformed input with backslashes
        if '\\' in text:
            return None

        text_lower = text.lower()

        # Require full path: linkedin.com/in/username (not just linkedin.com)
        if 'linkedin.com/in/' not in text_lower:
            return None

        # LinkedIn usernames: letters, numbers, and hyphens only (no underscores).
        # Capture including possible _ so we can reject; otherwise we'd truncate at _ (e.g. user_name -> user).
        # Minimum 2 characters, maximum 100 (match may be mid-message so no $ anchor).
        match = re.search(
            r'(https?://)?(www\.)?linkedin\.com/in/([a-zA-Z0-9\-_]{2,100})/?',
            text,
            re.IGNORECASE
        )
        if not match:
            return None

        username = match.group(3)
        if '_' in username or not re.match(r'^[a-zA-Z0-9\-]{2,100}$', username):
            return None

        url = match.group(0).rstrip('/')

        # Ensure https:// prefix
        if not url.lower().startswith('http'):
            url = 'https://' + url

        return url

    def _get_validation_error_message(self, error_type: str) -> str:
        """Return a fixed message for immediate validation feedback (same turn)."""
        if error_type == "email":
            return (
                "That doesn't look like a valid email address. We need a full address to continue, "
                "for example name@example.com. Could you please provide your email again?"
            )
        if error_type == "linkedin_url":
            return (
                "That doesn't look like a valid LinkedIn profile URL. We need a link to your profile "
                "to continue, for example https://linkedin.com/in/yourprofile. Could you please share it again?"
            )
        return "Please check your answer and try again."
    
    def _get_system_prompt(self, session: InterviewSession) -> str:
        """Generate the system prompt based on config and current state"""
        config = self.config
        
        # Get system context if available
        system_context = config.get('ai_config', {}).get('system_context', '')
        
        prompt = f"""You are {config['interview']['personality']['name']}, an AI interviewer for {config['company']['name']}.

ROLE: {config['role']['title']}
COMPANY: {config['company']['name']} - {config['company']['description']}

{f"ROLE CONTEXT: {config['role'].get('context', '')}" if config['role'].get('context') else ""}

YOUR INTERVIEW STYLE:
- Tone: {config['interview']['personality']['tone']}
- Style: {config['interview']['personality']['style']}

{system_context}

INTERVIEW PRINCIPLES:
{chr(10).join('- ' + p for p in config['interview'].get('principles', config['interview']['personality']['guidelines']))}

RED FLAGS TO WATCH FOR:
{chr(10).join('- ' + r for r in config['interview'].get('red_flags', []))}

COMPETENCIES YOU ARE ASSESSING:
"""
        for skill_id, skill in config['skills'].items():
            prompt += f"\n**{skill['name']}** (weight: {skill['weight']}/5):\n"
            prompt += f"  Description: {skill['description']}\n"
            prompt += f"  Looking for: {', '.join(skill['key_indicators'][:4])}\n"
            prompt += f"  Red flags: {', '.join(skill['red_flags'][:2])}\n"
            if skill.get('scoring_anchors'):
                prompt += f"  Score 5 = {skill['scoring_anchors'].get('5', '')}\n"
                prompt += f"  Score 3 = {skill['scoring_anchors'].get('3', '')}\n"
                prompt += f"  Score 1 = {skill['scoring_anchors'].get('1', '')}\n"

        prompt += f"""

CURRENT INTERVIEW STATE:
- Phase: {session.phase}
- Candidate Name: {session.candidate_name or 'Not yet collected'}
- Turn Count: {session.turn_count} / ~{config['interview'].get('max_turns', 30)} max
- Competencies Covered: {', '.join(session.skills_discussed) if session.skills_discussed else 'None yet'}
- Current Focus: {session.current_skill or 'None'}

CRITICAL RULES:
1. Ask ONE question at a time - never multiple questions
2. Keep responses concise (2-4 sentences max)
3. Briefly acknowledge good answers, then move on
4. When answers are VAGUE, probe for specifics:
   - "Can you give me specific numbers or metrics?"
   - "What tools did you actually use?"
   - "Walk me through the exact steps YOU took"
   - "What was the timeline?"
   - "What happened as a result?"
5. Use STAR format prompts when asking for examples:
   - Situation: What was the context?
   - Task: What were you trying to accomplish?
   - Action: What did YOU specifically do?
   - Result: What happened?
6. For PROMPTING EXERCISES: Give brief feedback, then ask them to improve
7. Never reveal scoring during the interview
8. If asked about salary, say the team will discuss that in later stages
9. Keep pace moving - aim for 20 minutes total
10. Be encouraging - this is junior screening, not senior grilling

{chr(10).join('- ' + i for i in config['ai_config'].get('additional_instructions', []))}
"""
        return prompt
    
    def _get_phase_instructions(self, session: InterviewSession) -> str:
        """Get specific instructions based on current phase"""
        config = self.config
        
        if session.phase == "introduction":
            return f"""
CURRENT PHASE: Introduction
Your task: Greet the candidate warmly and confirm they're ready to begin.
Opening message to use:
{config['conversation_flow']['introduction']['message']}

After they confirm, move to collecting their name."""

        elif session.phase == "collect_info":
            collected = list(session.collected_info.keys())
            # Use same collect_order logic as _update_session_state (ensure linkedin never skipped)
            base_order = config.get('conversation_flow', {}).get('collect_info', {}).get('order')
            required_fields = [f['field'] for f in config.get('required_info', [])]
            if base_order:
                collect_order = list(base_order)
                for f in required_fields:
                    if f not in collect_order:
                        collect_order.append(f)
            else:
                collect_order = required_fields
            needed = [f for f in collect_order if f not in collected]
            
            if not needed:
                return """
CURRENT PHASE: Transition to Interview
All required info collected. Transition smoothly with a brief intro like:
"Great! Let's jump in." Then start with the first competency area."""
            
            next_field = needed[0]
            field_config = next((f for f in config['required_info'] if f['field'] == next_field), None)
            if not field_config:
                field_config = {'field': next_field, 'question': f'Please provide your {next_field}.'}
            
            validation_hint = ""
            if session.last_validation_error == "email":
                validation_hint = '\nThe previous response did not look like a valid email address. Ask again and say we cannot continue the interview without a valid email (e.g. name@example.com).'
            elif session.last_validation_error == "linkedin_url":
                validation_hint = '\nThe previous response did not look like a LinkedIn profile URL. Ask again and say we cannot continue the interview without a valid LinkedIn profile link (e.g. https://linkedin.com/in/yourprofile).'
            
            return f"""
CURRENT PHASE: Collecting Required Information
You MUST ask for each of these in order. Do not skip any.
Still need to collect: {', '.join(needed)}
Next to collect: {next_field}
Question to ask (ask exactly this): "{field_config['question']}"{validation_hint}
"""

        elif session.phase == "skills_assessment":
            skills = list(config['skills'].keys())
            undiscussed = [s for s in skills if s not in session.skills_discussed]
            current_skill_config = config['skills'].get(session.current_skill, {})
            questions_on_current = session.questions_asked_per_skill.get(session.current_skill, 0)
            
            # Get phase-specific info if available
            phases = config.get('conversation_flow', {}).get('phases', [])
            current_phase_info = ""
            for phase in phases:
                phase_skills = phase.get('skills', [])
                if session.current_skill in phase_skills:
                    current_phase_info = f"""
Current Interview Section: {phase.get('name', '')}
Target Duration: {phase.get('duration_target', '')}
Questions to ask: {phase.get('question_count', 2)}
"""
                    if phase.get('intro'):
                        current_phase_info += f"Section intro: \"{phase['intro']}\"\n"
                    break
            
            # Get questions from the skill config
            questions_to_use = []
            if current_skill_config:
                # Check for different question types
                for q_type in ['warmup', 'core', 'exercise']:
                    q_list = current_skill_config.get('questions', {}).get(q_type, [])
                    for q in q_list:
                        if isinstance(q, dict):
                            questions_to_use.append(q)
                        elif isinstance(q, str):
                            questions_to_use.append({'question': q})
            
            # Also check for scenario intro
            scenario_intro = current_skill_config.get('questions', {}).get('scenario_intro', '')
            
            return f"""
CURRENT PHASE: Skills Assessment
{current_phase_info}

COMPETENCIES NOT YET DISCUSSED: {', '.join(undiscussed) if undiscussed else 'All covered!'}
CURRENT COMPETENCY: {current_skill_config.get('name', session.current_skill) or 'Pick one to start'}
Questions asked on current: {questions_on_current}
Description: {current_skill_config.get('description', '')}

{f"SCENARIO INTRO (use before questions): {scenario_intro}" if scenario_intro else ""}

SUGGESTED QUESTIONS FOR THIS COMPETENCY:
{chr(10).join(f"- {q.get('question', q)}" + (f" [Follow-up: {q.get('followup', '')}]" if q.get('followup') else "") for q in questions_to_use[:3])}

REMEMBER:
- Ask for SPECIFICS if answers are vague
- Use STAR format: Situation, Task, Action, Result
- For prompting exercises: Give brief feedback, ask them to improve
- After 2-3 questions on a competency, move to the next
- Total competencies: {len(skills)} | Covered: {len(session.skills_discussed)}
"""

        elif session.phase == "closing":
            if not session.closure_asked_questions:
                return f"""
CURRENT PHASE: Closing - Ask for candidate questions
Ask: "{config['conversation_flow']['closing'].get('candidate_questions_prompt', 'Do you have any questions for us?')}"
"""
            return f"""
CURRENT PHASE: Closing - Candidate just responded
1. If they ASKED questions: Acknowledge them by referencing what they asked (e.g. "I've noted your questions about [topic X] and [topic Y] - our team will be happy to discuss those in the next stages"). Show you took their questions into consideration. You do NOT need to answer the questions, only acknowledge that you understood and noted them.
2. If they declined (no questions): Skip the acknowledgment.
3. Then deliver the closing message:

{config['conversation_flow']['closing']['final_message'].replace('{name}', session.candidate_name)}
"""
        
        return ""
    
    def start_session(self, session_id: str) -> Tuple[str, InterviewSession]:
        """Start a new interview session"""
        session = InterviewSession(
            session_id=session_id,
            started_at=datetime.now().isoformat(),
            phase="introduction"
        )
        self.sessions[session_id] = session
        
        # Generate opening message
        opening = self.config['conversation_flow']['introduction']['message']
        
        session.conversation_history.append(ConversationTurn(
            role="assistant",
            content=opening,
            timestamp=datetime.now().isoformat(),
            metadata={"phase": "introduction"}
        ))
        session.turn_count += 1
        
        return opening, session
    
    def process_response(self, session_id: str, user_message: str) -> Tuple[str, InterviewSession]:
        """Process a candidate's response and generate the next message"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Add user message to history
        session.conversation_history.append(ConversationTurn(
            role="user",
            content=user_message,
            timestamp=datetime.now().isoformat(),
            metadata={"phase": session.phase}
        ))
        
        # Update session state based on response
        self._update_session_state(session, user_message)
        
        # When email or LinkedIn validation failed this turn, return a fixed message
        # immediately so the user gets feedback in the same turn (no AI reply that
        # thanks them and moves on).
        if session.last_validation_error:
            ai_response = self._get_validation_error_message(session.last_validation_error)
            session.conversation_history.append(ConversationTurn(
                role="assistant",
                content=ai_response,
                timestamp=datetime.now().isoformat(),
                metadata={"phase": session.phase, "validation_error": session.last_validation_error}
            ))
            session.turn_count += 1
            return ai_response, session
        
        # Check if interview should end
        if self._should_end_interview(session):
            session.phase = "complete"
            session.completed_at = datetime.now().isoformat()
            return self._generate_completion_message(session), session
        
        # Generate AI response
        ai_response = self._generate_response(session)
        
        # Add AI response to history
        session.conversation_history.append(ConversationTurn(
            role="assistant",
            content=ai_response,
            timestamp=datetime.now().isoformat(),
            metadata={"phase": session.phase, "current_skill": session.current_skill}
        ))
        session.turn_count += 1
        
        # Track that we asked for candidate questions; after ack+closing, end interview
        if session.phase == "closing":
            if not session.closure_asked_questions:
                session.closure_asked_questions = True
            else:
                session.phase = "complete"
                session.completed_at = datetime.now().isoformat()
        
        return ai_response, session
    
    def _update_session_state(self, session: InterviewSession, user_message: str):
        """Update session state based on user response"""
        config = self.config
        
        # Handle introduction phase
        if session.phase == "introduction":
            # Any response moves us to collect_info
            session.phase = "collect_info"
            return
        
        # Handle info collection
        if session.phase == "collect_info":
            collected = list(session.collected_info.keys())
            # Use explicit collect order - ensure linkedin_url is never skipped
            base_order = config.get('conversation_flow', {}).get('collect_info', {}).get('order')
            required_fields = [f['field'] for f in config.get('required_info', [])]
            if base_order:
                collect_order = list(base_order)
                for f in required_fields:
                    if f not in collect_order:
                        collect_order.append(f)
            else:
                collect_order = required_fields
            needed_fields = [f for f in collect_order if f not in collected]
            session.last_validation_error = ""  # Clear on each new response
            
            if needed_fields:
                msg = user_message.strip()
                next_field = needed_fields[0]

                # When we're asking for email, treat any message containing "@" as an email
                # attempt and validate immediately. Never accept or move on without valid email.
                if next_field == "email" and "@" in msg:
                    extracted = self._extract_email(msg)
                    if not extracted:
                        session.last_validation_error = "email"
                        return
                    # Valid email: assign and continue
                    session.collected_info["email"] = extracted
                    session.candidate_email = extracted
                    # Fall through to still_needed check below (don't run generic assignment)
                elif next_field == "linkedin_url" and "linkedin.com" in msg.lower():
                    # When we're asking for LinkedIn, validate any message that mentions linkedin
                    extracted = self._extract_linkedin_url(msg)
                    if not extracted:
                        session.last_validation_error = "linkedin_url"
                        return
                    session.collected_info["linkedin_url"] = extracted
                    session.candidate_linkedin = extracted
                else:
                    # Content-based assignment for other cases
                    target_field = None
                    _linkedin_in_msg = "linkedin.com/in/" in msg.lower()
                    _email_match = re.search(
                        r'[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                        msg
                    )
                    if _linkedin_in_msg and "linkedin_url" in needed_fields:
                        target_field = "linkedin_url"
                    elif _email_match and "email" in needed_fields:
                        target_field = "email"
                    elif "name" in needed_fields and not (_linkedin_in_msg or "@" in msg):
                        target_field = "name"
                    if target_field is None:
                        target_field = needed_fields[0]

                    # Validate email and LinkedIn before accepting
                    if target_field == "email":
                        extracted = self._extract_email(msg)
                        if not extracted:
                            session.last_validation_error = "email"
                            return
                        msg = extracted
                    elif target_field == "linkedin_url":
                        extracted = self._extract_linkedin_url(msg)
                        if not extracted:
                            session.last_validation_error = "linkedin_url"
                            return
                        msg = extracted

                    session.collected_info[target_field] = msg
                    if target_field == "name":
                        session.candidate_name = msg
                    elif target_field == "email":
                        session.candidate_email = msg
                    elif target_field == "linkedin_url":
                        session.candidate_linkedin = msg
                    elif target_field == "location":
                        session.candidate_location = msg
                    elif target_field == "availability":
                        session.candidate_availability = msg
            
            # Check if all info collected (never skip linkedin_url if it's required)
            still_needed = [f for f in collect_order if f not in session.collected_info]
            if not still_needed:
                session.phase = "skills_assessment"
            return
        
        # Handle skills assessment
        if session.phase == "skills_assessment":
            # Record response for current skill
            if session.current_skill:
                if session.current_skill not in session.skill_responses:
                    session.skill_responses[session.current_skill] = []
                session.skill_responses[session.current_skill].append({
                    "question": session.conversation_history[-2].content if len(session.conversation_history) >= 2 else "",
                    "answer": user_message,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Update question count
                session.questions_asked_per_skill[session.current_skill] = \
                    session.questions_asked_per_skill.get(session.current_skill, 0) + 1
                
                # Mark skill as discussed if not already
                if session.current_skill not in session.skills_discussed:
                    session.skills_discussed.append(session.current_skill)
            
            # Check if ready to close
            all_skills = list(config['skills'].keys())
            if len(session.skills_discussed) >= len(all_skills) * 0.7:  # 70% of skills covered
                if session.turn_count >= config['interview']['min_responses']:
                    session.phase = "closing"
            return
        
        # Handle closing phase: do NOT transition here - let AI acknowledge
        # the candidate's questions first, then we complete after AI responds
        if session.phase == "closing":
            return
    
    def _should_end_interview(self, session: InterviewSession) -> bool:
        """Check if the interview should end"""
        config = self.config
        
        if session.phase == "complete":
            return True
        
        if session.turn_count >= config['interview']['max_turns']:
            return True
        
        return False
    
    def _generate_response(self, session: InterviewSession) -> str:
        """Generate AI response using OpenAI"""
        config = self.config['ai_config']
        
        # Build messages for OpenAI
        messages = [
            {"role": "system", "content": self._get_system_prompt(session)},
            {"role": "system", "content": self._get_phase_instructions(session)}
        ]
        
        # Add conversation history (last 20 turns for context window)
        for turn in session.conversation_history[-20:]:
            messages.append({
                "role": turn.role if turn.role == "user" else "assistant",
                "content": turn.content
            })
        
        # Determine next skill to focus on (for skills assessment phase)
        if session.phase == "skills_assessment":
            next_skill = self._select_next_skill(session)
            session.current_skill = next_skill
            messages.append({
                "role": "system",
                "content": f"Focus your next question on assessing: {next_skill}"
            })
        
        try:
            response = self.client.chat.completions.create(
                model=config['model'],
                messages=messages,
                temperature=config['temperature'],
                max_tokens=config['max_tokens']
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return "I apologize, I'm having a technical difficulty. Could you please repeat your last response?"
    
    def _select_next_skill(self, session: InterviewSession) -> str:
        """Select the next skill to assess"""
        config = self.config
        skills = list(config['skills'].keys())
        
        # Prioritize skills not yet discussed
        undiscussed = [s for s in skills if s not in session.skills_discussed]
        if undiscussed:
            # Prioritize by weight
            undiscussed.sort(key=lambda s: config['skills'][s]['weight'], reverse=True)
            return undiscussed[0]
        
        # If all discussed, pick one with fewest questions
        min_questions = min(session.questions_asked_per_skill.get(s, 0) for s in skills)
        candidates = [s for s in skills if session.questions_asked_per_skill.get(s, 0) == min_questions]
        return candidates[0] if candidates else skills[0]
    
    def _generate_completion_message(self, session: InterviewSession) -> str:
        """Generate the final completion message"""
        config = self.config
        message = config['conversation_flow']['closing']['final_message']
        return message.replace('{name}', session.candidate_name or 'there')
    
    def evaluate_candidate(self, session_id: str) -> CandidateEvaluation:
        """Generate a comprehensive evaluation of the candidate"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        config = self.config
        
        # Build evaluation prompt
        eval_prompt = self._build_evaluation_prompt(session)
        
        # Define the structured output schema
        eval_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "candidate_evaluation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "skill_scores": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "skill_id": {"type": "string"},
                                    "score": {"type": "integer", "minimum": 1, "maximum": 5},
                                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                                    "evidence": {"type": "array", "items": {"type": "string"}},
                                    "concerns": {"type": "array", "items": {"type": "string"}},
                                    "follow_up_needed": {"type": "boolean"},
                                    "follow_up_questions": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["skill_id", "score", "confidence", "evidence", "concerns", "follow_up_needed", "follow_up_questions"],
                                "additionalProperties": False
                            }
                        },
                        "strengths": {"type": "array", "items": {"type": "string"}},
                        "concerns": {"type": "array", "items": {"type": "string"}},
                        "overall_summary": {"type": "string"},
                        "followup_focus_areas": {"type": "array", "items": {"type": "string"}},
                        "followup_questions": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["skill_scores", "strengths", "concerns", "overall_summary", "followup_focus_areas", "followup_questions"],
                    "additionalProperties": False
                }
            }
        }
        
        try:
            # Use model from config
            model = config.get('ai_config', {}).get('model', 'gpt-4o')
            
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": eval_prompt}
                ],
                response_format=eval_schema,
                temperature=0.3  # Lower temperature for more consistent evaluation
            )
            
            eval_data = json.loads(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Evaluation error: {e}")
            # Return a default evaluation on error
            eval_data = self._default_evaluation()
        
        # Calculate weighted average
        skill_scores = {}
        total_weight = 0
        weighted_sum = 0
        
        for score_data in eval_data['skill_scores']:
            skill_id = score_data['skill_id']
            skill_config = config['skills'].get(skill_id, {})
            weight = skill_config.get('weight', 1)
            
            skill_scores[skill_id] = SkillScore(
                skill_id=skill_id,
                skill_name=skill_config.get('name', skill_id),
                score=score_data['score'],
                confidence=score_data['confidence'],
                evidence=score_data['evidence'],
                concerns=score_data['concerns'],
                follow_up_needed=score_data['follow_up_needed'],
                follow_up_questions=score_data['follow_up_questions']
            )
            
            weighted_sum += score_data['score'] * weight
            total_weight += weight
        
        weighted_average = weighted_sum / total_weight if total_weight > 0 else 0
        
        # Determine recommendation
        recommendation, rec_label, rec_desc = self._get_recommendation(weighted_average)
        
        return CandidateEvaluation(
            candidate_name=session.candidate_name,
            candidate_email=session.candidate_email,
            candidate_linkedin=session.candidate_linkedin or "",
            interview_date=session.started_at,
            role=config['role']['title'],
            skill_scores=skill_scores,
            weighted_average=round(weighted_average, 2),
            recommendation=recommendation,
            recommendation_label=rec_label,
            recommendation_description=rec_desc,
            strengths=eval_data['strengths'],
            concerns=eval_data['concerns'],
            overall_summary=eval_data['overall_summary'],
            recommended_for_followup=recommendation in ['strong_yes', 'yes'],
            followup_focus_areas=eval_data['followup_focus_areas'],
            followup_questions=eval_data['followup_questions']
        )
    
    def _build_evaluation_prompt(self, session: InterviewSession) -> str:
        """Build the prompt for candidate evaluation"""
        config = self.config
        
        prompt = f"""You are evaluating a candidate interview for the {config['role']['title']} position at {config['company']['name']}.

ROLE CONTEXT:
{config['role'].get('context', 'B2B marketing role')}

SCORING RUBRIC (1-5):
"""
        for score, rubric in config['scoring_rubric'].items():
            prompt += f"\n{score} - {rubric['label']}: {rubric['description']}\n"
        
        prompt += "\n\nCOMPETENCIES TO EVALUATE:\n"
        for skill_id, skill in config['skills'].items():
            prompt += f"\n**{skill_id}** - {skill['name']} (weight: {skill['weight']}/5):\n"
            prompt += f"  Description: {skill['description']}\n"
            prompt += f"  Looking for: {', '.join(skill['key_indicators'][:4])}\n"
            prompt += f"  Red flags: {', '.join(skill['red_flags'][:3])}\n"
            if skill.get('scoring_anchors'):
                prompt += f"  5 = {skill['scoring_anchors'].get('5', '')}\n"
                prompt += f"  3 = {skill['scoring_anchors'].get('3', '')}\n"
                prompt += f"  1 = {skill['scoring_anchors'].get('1', '')}\n"
        
        prompt += "\n\nRED FLAGS TO WATCH FOR:\n"
        for flag in config['interview'].get('red_flags', []):
            prompt += f"- {flag}\n"
        
        prompt += "\n\n" + "=" * 60 + "\n"
        prompt += "INTERVIEW TRANSCRIPT\n"
        prompt += "=" * 60 + "\n"
        
        for turn in session.conversation_history:
            role_label = "INTERVIEWER" if turn.role == "assistant" else "CANDIDATE"
            prompt += f"\n[{role_label}]: {turn.content}\n"
        
        prompt += "\n" + "=" * 60 + "\n"
        
        prompt += """

EVALUATION INSTRUCTIONS:

Based on this transcript, provide a structured evaluation following these requirements:

1. SCORE EACH COMPETENCY (1-5):
   - Score based ONLY on evidence from the transcript
   - If a competency wasn't discussed much, give score 3 with low confidence
   - Use the scoring anchors provided for each competency
   - Quote or paraphrase specific candidate statements as evidence

2. IDENTIFY:
   - 3 clear STRENGTHS observed (with evidence)
   - 3 RISKS or CONCERNS (with evidence)
   - Note any RED FLAGS you observed

3. GENERATE:
   - 3 recommended next-step checks (work sample, reference question, or interview focus area)
   - 5-7 specific follow-up questions for areas needing deeper exploration

4. FINAL RECOMMENDATION:
   - Strong Yes (score >= 4.0): Strong junior potential, proceed to final interview
   - Yes (score >= 3.3): Good potential, needs follow-up on specific areas
   - Maybe (score >= 2.5): Some potential but significant questions remain
   - No (score < 2.5): Does not meet requirements

REMEMBER:
- This is JUNIOR screening - don't penalize lack of senior experience
- Look for potential and fundamentals, not perfection
- Note what was DEMONSTRATED vs what was only CLAIMED
- Be fair but objective
"""
        return prompt
    
    def _get_recommendation(self, weighted_average: float) -> Tuple[str, str, str]:
        """Get recommendation based on weighted average score"""
        try:
            recommendations = self.config.get('recommendations', {})
            
            # Debug logging
            print(f"[DEBUG] Recommendations keys: {list(recommendations.keys())}")
            print(f"[DEBUG] Weighted average: {weighted_average}")
            
            # Handle potential YAML boolean conversion (yes -> True)
            # YAML can convert 'yes'/'no' to True/False
            strong_yes = recommendations.get('strong_yes') or recommendations.get(True)
            yes_rec = recommendations.get('yes') or recommendations.get(True)
            maybe_rec = recommendations.get('maybe')
            no_rec = recommendations.get('no') or recommendations.get(False)
            
            if strong_yes and weighted_average >= strong_yes.get('min_weighted_score', 4.0):
                return 'strong_yes', strong_yes.get('label', 'Strong Yes'), strong_yes.get('description', '')
            elif yes_rec and weighted_average >= yes_rec.get('min_weighted_score', 3.2):
                return 'yes', yes_rec.get('label', 'Yes'), yes_rec.get('description', '')
            elif maybe_rec and weighted_average >= maybe_rec.get('min_weighted_score', 2.3):
                return 'maybe', maybe_rec.get('label', 'Maybe'), maybe_rec.get('description', '')
            else:
                if no_rec:
                    return 'no', no_rec.get('label', 'No'), no_rec.get('description', '')
                return 'no', 'No', 'Does not meet requirements'
                
        except Exception as e:
            print(f"[ERROR] _get_recommendation failed: {e}")
            print(f"[ERROR] Config recommendations: {self.config.get('recommendations')}")
            return 'error', 'Review Needed', f'Recommendation error: {e}'
    
    def _default_evaluation(self) -> Dict:
        """Return default evaluation structure on error"""
        return {
            "skill_scores": [],
            "strengths": ["Unable to fully evaluate - please review transcript manually"],
            "concerns": ["Evaluation error occurred"],
            "overall_summary": "Automatic evaluation failed. Please review the interview transcript manually.",
            "followup_focus_areas": ["All areas"],
            "followup_questions": ["Please conduct a full follow-up interview"]
        }
    
    def generate_followup_guide(self, evaluation: CandidateEvaluation) -> str:
        """Generate a guide for the human follow-up interviewer"""
        config = self.config
        
        guide = f"""
{'='*60}
FOLLOW-UP INTERVIEW GUIDE
{'='*60}

CANDIDATE: {evaluation.candidate_name}
EMAIL: {evaluation.candidate_email}
INITIAL INTERVIEW: {evaluation.interview_date}
AI RECOMMENDATION: {evaluation.recommendation_label}

{'='*60}
OVERALL SUMMARY
{'='*60}
{evaluation.overall_summary}

WEIGHTED SCORE: {evaluation.weighted_average}/5.0

{'='*60}
STRENGTHS OBSERVED
{'='*60}
"""
        for strength in evaluation.strengths:
            guide += f"✓ {strength}\n"
        
        guide += f"""
{'='*60}
AREAS OF CONCERN
{'='*60}
"""
        for concern in evaluation.concerns:
            guide += f"⚠ {concern}\n"
        
        guide += f"""
{'='*60}
SKILL BREAKDOWN
{'='*60}
"""
        for skill_id, score in evaluation.skill_scores.items():
            guide += f"\n{score.skill_name}: {score.score}/5 (confidence: {score.confidence:.0%})\n"
            if score.evidence:
                guide += f"  Evidence: {score.evidence[0]}\n"
            if score.concerns:
                guide += f"  Concern: {score.concerns[0]}\n"
            if score.follow_up_needed:
                guide += f"  ⚡ NEEDS FOLLOW-UP\n"
        
        guide += f"""
{'='*60}
RECOMMENDED FOCUS AREAS FOR FOLLOW-UP
{'='*60}
"""
        for area in evaluation.followup_focus_areas:
            guide += f"→ {area}\n"
        
        guide += f"""
{'='*60}
SUGGESTED FOLLOW-UP QUESTIONS
{'='*60}
"""
        for i, question in enumerate(evaluation.followup_questions, 1):
            guide += f"{i}. {question}\n"
        
        guide += f"""
{'='*60}
INTERVIEW GUIDELINES
{'='*60}
"""
        for guideline in config['follow_up_interview']['interviewer_guidelines']:
            guide += f"• {guideline}\n"
        
        return guide
    
    def get_session(self, session_id: str) -> Optional[InterviewSession]:
        """Get a session by ID"""
        return self.sessions.get(session_id)
    
    def export_session(self, session_id: str) -> Dict:
        """Export session data as dictionary"""
        session = self.sessions.get(session_id)
        if not session:
            return {}
        
        return {
            "session_id": session.session_id,
            "candidate_name": session.candidate_name,
            "candidate_email": session.candidate_email,
            "candidate_linkedin": session.candidate_linkedin,
            "candidate_location": session.candidate_location,
            "candidate_availability": session.candidate_availability,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "turn_count": session.turn_count,
            "phase": session.phase,
            "conversation_history": [
                {
                    "role": turn.role,
                    "content": turn.content,
                    "timestamp": turn.timestamp,
                    "metadata": turn.metadata
                }
                for turn in session.conversation_history
            ],
            "collected_info": session.collected_info,
            "skills_discussed": session.skills_discussed,
            "skill_responses": session.skill_responses
        }


# =============================================================================
# FOLLOW-UP INTERVIEW ENGINE
# =============================================================================

class FollowUpInterviewEngine:
    """
    Engine for conducting AI-assisted follow-up interviews.
    Uses the initial evaluation to guide deeper exploration.
    """
    
    def __init__(self, config_path: str = "interview_guidelines.yaml"):
        self.config = self._load_config(config_path)
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.sessions: Dict[str, Dict] = {}
    
    def _load_config(self, config_path: str) -> Dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def start_followup_session(
        self, 
        session_id: str, 
        evaluation: CandidateEvaluation,
        initial_transcript: List[Dict]
    ) -> Tuple[str, Dict]:
        """Start a follow-up interview session"""
        
        session = {
            "session_id": session_id,
            "candidate_name": evaluation.candidate_name,
            "candidate_email": evaluation.candidate_email,
            "initial_evaluation": asdict(evaluation),
            "initial_transcript": initial_transcript,
            "followup_conversation": [],
            "focus_areas": evaluation.followup_focus_areas,
            "suggested_questions": evaluation.followup_questions,
            "started_at": datetime.now().isoformat(),
            "phase": "introduction"
        }
        
        self.sessions[session_id] = session
        
        opening = f"""Welcome back, {evaluation.candidate_name}! Thank you for joining us for this follow-up conversation.

Based on our initial interview, I'd like to dive deeper into a few areas. This will help us get a better understanding of your experience and how you might fit with our team.

Let's start by exploring your {evaluation.followup_focus_areas[0] if evaluation.followup_focus_areas else 'background'} in more detail."""
        
        session['followup_conversation'].append({
            "role": "assistant",
            "content": opening,
            "timestamp": datetime.now().isoformat()
        })
        
        return opening, session
    
    def process_followup_response(self, session_id: str, user_message: str) -> Tuple[str, Dict]:
        """Process a response in the follow-up interview"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        session['followup_conversation'].append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Generate response
        response = self._generate_followup_response(session)
        
        session['followup_conversation'].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat()
        })
        
        return response, session
    
    def _generate_followup_response(self, session: Dict) -> str:
        """Generate AI response for follow-up interview"""
        eval_data = session['initial_evaluation']
        
        system_prompt = f"""You are conducting a follow-up interview for {session['candidate_name']} for the {self.config['role']['title']} position.

INITIAL EVALUATION SUMMARY:
- Recommendation: {eval_data['recommendation_label']}
- Score: {eval_data['weighted_average']}/5
- Strengths: {', '.join(eval_data['strengths'][:3])}
- Concerns: {', '.join(eval_data['concerns'][:3])}

AREAS TO EXPLORE IN THIS FOLLOW-UP:
{chr(10).join('- ' + area for area in session['focus_areas'])}

SUGGESTED QUESTIONS TO ASK:
{chr(10).join('- ' + q for q in session['suggested_questions'][:5])}

YOUR TASK:
1. Ask probing questions to verify or clarify the initial assessment
2. Dig deeper into concerning areas
3. Get more specific examples for strong claims
4. Assess culture fit and working style
5. Keep the conversation natural and flowing

Remember: This is a follow-up, so reference their earlier responses when relevant.
Keep responses concise. Ask ONE question at a time."""

        messages = [{"role": "system", "content": system_prompt}]
        
        # Add follow-up conversation history
        for turn in session['followup_conversation'][-15:]:
            messages.append({
                "role": turn['role'] if turn['role'] == 'user' else 'assistant',
                "content": turn['content']
            })
        
        try:
            response = self.client.chat.completions.create(
                model=self.config['ai_config']['model'],
                messages=messages,
                temperature=0.7,
                max_tokens=400
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return "I apologize for the technical difficulty. Could you please repeat that?"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def evaluation_to_dict(evaluation: CandidateEvaluation) -> Dict:
    """Convert evaluation to dictionary for JSON serialization"""
    return {
        "candidate_name": evaluation.candidate_name,
        "candidate_email": evaluation.candidate_email,
        "candidate_linkedin": evaluation.candidate_linkedin or "",
        "interview_date": evaluation.interview_date,
        "role": evaluation.role,
        "skill_scores": {
            k: {
                "skill_id": v.skill_id,
                "skill_name": v.skill_name,
                "score": v.score,
                "confidence": v.confidence,
                "evidence": v.evidence,
                "concerns": v.concerns,
                "follow_up_needed": v.follow_up_needed,
                "follow_up_questions": v.follow_up_questions
            }
            for k, v in evaluation.skill_scores.items()
        },
        "weighted_average": evaluation.weighted_average,
        "recommendation": evaluation.recommendation,
        "recommendation_label": evaluation.recommendation_label,
        "recommendation_description": evaluation.recommendation_description,
        "strengths": evaluation.strengths,
        "concerns": evaluation.concerns,
        "overall_summary": evaluation.overall_summary,
        "recommended_for_followup": evaluation.recommended_for_followup,
        "followup_focus_areas": evaluation.followup_focus_areas,
        "followup_questions": evaluation.followup_questions
    }
