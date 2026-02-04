"""
Nytro Junior Marketer Interview Chatbot - Flask Web Application
AI-Powered Interview System with OpenAI Integration
"""

import os
import json
import uuid
import requests
from datetime import datetime
from functools import wraps

# Load environment variables from .env file (for local development)
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from ai_interview_engine import (
    AIInterviewEngine, 
    FollowUpInterviewEngine,
    CandidateEvaluation,
    evaluation_to_dict
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configuration
HUBSPOT_ACCESS_TOKEN = os.environ.get('HUBSPOT_ACCESS_TOKEN')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'nytro-admin-2024')  # Change in production!

# Initialize AI engines
try:
    ai_engine = AIInterviewEngine(config_path="interview_guidelines.yaml")
    followup_engine = FollowUpInterviewEngine(config_path="interview_guidelines.yaml")
    AI_ENABLED = True
except Exception as e:
    print(f"Warning: AI engine failed to initialize: {e}")
    print("Running in fallback mode without AI features.")
    AI_ENABLED = False
    ai_engine = None
    followup_engine = None

# In-memory storage for evaluations (use database in production)
completed_evaluations = {}
followup_sessions = {}


# =============================================================================
# HUBSPOT INTEGRATION
# =============================================================================

def get_hubspot_headers():
    """Get headers for HubSpot API requests"""
    return {
        "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }


def search_contact_by_email(email: str) -> dict:
    """Search for an existing contact by email"""
    if not HUBSPOT_ACCESS_TOKEN:
        return None
        
    url = "https://api.hubapi.com/crm/v3/objects/contacts/search"
    payload = {
        "filterGroups": [{
            "filters": [{
                "propertyName": "email",
                "operator": "EQ",
                "value": email
            }]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=get_hubspot_headers())
        response.raise_for_status()
        data = response.json()
        if data.get("total", 0) > 0:
            return data["results"][0]
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error searching contact: {e}")
        return None


def create_contact(name: str, email: str, city: str = None) -> dict:
    """Create a new contact in HubSpot"""
    if not HUBSPOT_ACCESS_TOKEN:
        return None
        
    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    name_parts = name.strip().split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    properties = {
        "email": email,
        "firstname": first_name,
        "lastname": last_name
    }
    if city:
        properties["city"] = city
    
    try:
        response = requests.post(url, json={"properties": properties}, headers=get_hubspot_headers())
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating contact: {e}")
        return None


def create_note(contact_id: str, note_body: str) -> dict:
    """Create a note and associate it with a contact"""
    if not HUBSPOT_ACCESS_TOKEN:
        return None
        
    url = "https://api.hubapi.com/crm/v3/objects/notes"
    payload = {
        "properties": {
            "hs_timestamp": str(int(datetime.now().timestamp() * 1000)),  # Unix ms
            "hs_note_body": note_body
        },
        "associations": [{
            "to": {"id": contact_id},
            "types": [{
                "associationCategory": "HUBSPOT_DEFINED",
                "associationTypeId": 202
            }]
        }]
    }
    
    try:
        response = requests.post(url, json=payload, headers=get_hubspot_headers())
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating note: {e}")
        return None


def format_evaluation_note(evaluation: CandidateEvaluation, transcript: list) -> str:
    """Format evaluation into an HTML note for HubSpot"""
    note = f"""
<h2>AI Interview - {evaluation.candidate_name}</h2>
<p><strong>Date:</strong> {evaluation.interview_date}</p>
<p><strong>Position:</strong> {evaluation.role}</p>
<p><strong>AI Recommendation:</strong> {evaluation.recommendation_label}</p>
<p><strong>Score:</strong> {evaluation.weighted_average}/5.0</p>

<hr>

<h3>Summary</h3>
<p>{evaluation.overall_summary}</p>

<h3>Strengths</h3>
<ul>
{"".join(f"<li>{s}</li>" for s in evaluation.strengths)}
</ul>

<h3>Concerns</h3>
<ul>
{"".join(f"<li>{c}</li>" for c in evaluation.concerns)}
</ul>

<h3>Skill Scores</h3>
<ul>
"""
    for skill_id, score in evaluation.skill_scores.items():
        note += f"<li><strong>{score.skill_name}:</strong> {score.score}/5"
        if score.follow_up_needed:
            note += " ⚡ Follow-up needed"
        note += "</li>\n"
    
    note += """
</ul>

<h3>Recommended Follow-up Questions</h3>
<ol>
"""
    for q in evaluation.followup_questions[:5]:
        note += f"<li>{q}</li>\n"
    
    note += """
</ol>

<hr>
<p><em>This interview was conducted via the Nytro AI Interview Chatbot.</em></p>
"""
    return note


def send_evaluation_to_hubspot(evaluation: CandidateEvaluation, transcript: list) -> dict:
    """Send evaluation to HubSpot"""
    print(f"[HubSpot] Attempting to send evaluation for {evaluation.candidate_name} ({evaluation.candidate_email})")
    
    if not HUBSPOT_ACCESS_TOKEN:
        print("[HubSpot] ERROR: No access token configured")
        return {"success": False, "error": "HubSpot not configured"}
    
    if not evaluation.candidate_email:
        print("[HubSpot] ERROR: No email provided")
        return {"success": False, "error": "No email provided"}
    
    # Find or create contact
    contact = search_contact_by_email(evaluation.candidate_email)
    if contact:
        contact_id = contact["id"]
        print(f"[HubSpot] Found existing contact: {contact_id}")
    else:
        print(f"[HubSpot] Creating new contact...")
        contact = create_contact(
            evaluation.candidate_name, 
            evaluation.candidate_email
        )
        if not contact:
            print("[HubSpot] ERROR: Failed to create contact")
            return {"success": False, "error": "Failed to create contact"}
        contact_id = contact["id"]
        print(f"[HubSpot] Created contact: {contact_id}")
    
    # Create note with evaluation
    print(f"[HubSpot] Creating note for contact {contact_id}...")
    note_body = format_evaluation_note(evaluation, transcript)
    note = create_note(contact_id, note_body)
    
    if not note:
        print("[HubSpot] ERROR: Failed to create note")
        return {"success": False, "error": "Failed to create note"}
    
    print(f"[HubSpot] SUCCESS: Note created with ID {note.get('id')}")
    
    return {
        "success": True,
        "message": "Evaluation saved to HubSpot",
        "contact_id": contact_id,
        "note_id": note["id"]
    }


# =============================================================================
# ADMIN AUTHENTICATION
# =============================================================================

def admin_required(f):
    """Decorator to require admin authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_authenticated'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function


# =============================================================================
# PUBLIC ROUTES - CANDIDATE INTERVIEW
# =============================================================================

@app.route('/')
def index():
    """Serve the interview chatbot page"""
    return render_template('index.html', ai_enabled=AI_ENABLED)


@app.route('/api/start', methods=['POST'])
def start_interview():
    """Start a new interview session"""
    if not AI_ENABLED:
        return jsonify({"success": False, "error": "AI features not available"}), 503
    
    session_id = str(uuid.uuid4())
    session['interview_session_id'] = session_id
    
    try:
        opening_message, interview_session = ai_engine.start_session(session_id)
        
        return jsonify({
            "success": True,
            "message": opening_message,
            "session_id": session_id,
            "phase": interview_session.phase
        })
    except Exception as e:
        print(f"Error starting interview: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/respond', methods=['POST'])
def process_response():
    """Process a candidate's response"""
    if not AI_ENABLED:
        return jsonify({"success": False, "error": "AI features not available"}), 503
    
    data = request.get_json()
    response_text = data.get('response', '').strip()
    
    if not response_text:
        return jsonify({"success": False, "error": "Please provide an answer"})
    
    session_id = session.get('interview_session_id')
    if not session_id:
        return jsonify({"success": False, "error": "No active session"})
    
    try:
        ai_response, interview_session = ai_engine.process_response(session_id, response_text)
        
        response_data = {
            "success": True,
            "message": ai_response,
            "phase": interview_session.phase,
            "turn_count": interview_session.turn_count,
            "complete": interview_session.phase == "complete"
        }
        
        # If interview is complete, generate evaluation
        if interview_session.phase == "complete":
            try:
                evaluation = ai_engine.evaluate_candidate(session_id)
                session_data = ai_engine.export_session(session_id)
                
                # Store evaluation
                completed_evaluations[session_id] = {
                    "evaluation": evaluation_to_dict(evaluation),
                    "session_data": session_data,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Send to HubSpot
                hubspot_result = send_evaluation_to_hubspot(
                    evaluation, 
                    session_data.get('conversation_history', [])
                )
                
                response_data["evaluation_summary"] = {
                    "recommendation": evaluation.recommendation_label,
                    "score": evaluation.weighted_average,
                    "summary": evaluation.overall_summary[:200] + "..."
                }
                response_data["hubspot"] = hubspot_result
                
            except Exception as e:
                print(f"Evaluation error: {e}")
                response_data["evaluation_error"] = str(e)
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error processing response: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/progress', methods=['GET'])
def get_progress():
    """Get current interview progress"""
    session_id = session.get('interview_session_id')
    if not session_id or not AI_ENABLED:
        return jsonify({"phase": "not_started", "turn_count": 0})
    
    interview_session = ai_engine.get_session(session_id)
    if not interview_session:
        return jsonify({"phase": "not_started", "turn_count": 0})
    
    return jsonify({
        "phase": interview_session.phase,
        "turn_count": interview_session.turn_count,
        "skills_covered": len(interview_session.skills_discussed)
    })


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "ai_enabled": AI_ENABLED,
        "timestamp": datetime.now().isoformat()
    })


# =============================================================================
# ADMIN ROUTES - DASHBOARD
# =============================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_authenticated'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin_login.html', error="Invalid password")
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_authenticated', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard showing all evaluations"""
    evaluations = []
    for session_id, data in completed_evaluations.items():
        eval_data = data['evaluation']
        evaluations.append({
            "session_id": session_id,
            "candidate_name": eval_data['candidate_name'],
            "candidate_email": eval_data['candidate_email'],
            "recommendation": eval_data['recommendation'],
            "recommendation_label": eval_data['recommendation_label'],
            "score": eval_data['weighted_average'],
            "timestamp": data['timestamp']
        })
    
    # Sort by timestamp descending
    evaluations.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return render_template('admin_dashboard.html', evaluations=evaluations)


@app.route('/admin/evaluation/<session_id>')
@admin_required
def view_evaluation(session_id):
    """View detailed evaluation for a candidate"""
    data = completed_evaluations.get(session_id)
    if not data:
        return "Evaluation not found", 404
    
    return render_template(
        'admin_evaluation.html',
        evaluation=data['evaluation'],
        session_data=data['session_data'],
        session_id=session_id
    )


@app.route('/admin/evaluation/<session_id>/followup-guide')
@admin_required
def get_followup_guide(session_id):
    """Generate follow-up interview guide"""
    data = completed_evaluations.get(session_id)
    if not data:
        return jsonify({"error": "Evaluation not found"}), 404
    
    eval_data = data['evaluation']
    
    # Reconstruct CandidateEvaluation from dict
    from ai_interview_engine import SkillScore
    
    skill_scores = {}
    for skill_id, score_data in eval_data['skill_scores'].items():
        skill_scores[skill_id] = SkillScore(
            skill_id=score_data['skill_id'],
            skill_name=score_data['skill_name'],
            score=score_data['score'],
            confidence=score_data['confidence'],
            evidence=score_data['evidence'],
            concerns=score_data['concerns'],
            follow_up_needed=score_data['follow_up_needed'],
            follow_up_questions=score_data['follow_up_questions']
        )
    
    evaluation = CandidateEvaluation(
        candidate_name=eval_data['candidate_name'],
        candidate_email=eval_data['candidate_email'],
        interview_date=eval_data['interview_date'],
        role=eval_data['role'],
        skill_scores=skill_scores,
        weighted_average=eval_data['weighted_average'],
        recommendation=eval_data['recommendation'],
        recommendation_label=eval_data['recommendation_label'],
        recommendation_description=eval_data['recommendation_description'],
        strengths=eval_data['strengths'],
        concerns=eval_data['concerns'],
        overall_summary=eval_data['overall_summary'],
        recommended_for_followup=eval_data['recommended_for_followup'],
        followup_focus_areas=eval_data['followup_focus_areas'],
        followup_questions=eval_data['followup_questions']
    )
    
    guide = ai_engine.generate_followup_guide(evaluation)
    
    return jsonify({"guide": guide})


@app.route('/admin/followup/<session_id>')
@admin_required
def followup_interview(session_id):
    """Page for conducting follow-up interview"""
    data = completed_evaluations.get(session_id)
    if not data:
        return "Evaluation not found", 404
    
    return render_template(
        'admin_followup.html',
        evaluation=data['evaluation'],
        session_data=data['session_data'],
        original_session_id=session_id
    )


@app.route('/api/admin/followup/start', methods=['POST'])
@admin_required
def start_followup():
    """Start a follow-up interview session"""
    if not AI_ENABLED:
        return jsonify({"success": False, "error": "AI features not available"}), 503
    
    data = request.get_json()
    original_session_id = data.get('original_session_id')
    
    eval_data = completed_evaluations.get(original_session_id)
    if not eval_data:
        return jsonify({"success": False, "error": "Original evaluation not found"}), 404
    
    # Create new follow-up session
    followup_session_id = str(uuid.uuid4())
    
    # Reconstruct evaluation object
    from ai_interview_engine import SkillScore
    
    skill_scores = {}
    for skill_id, score_data in eval_data['evaluation']['skill_scores'].items():
        skill_scores[skill_id] = SkillScore(**score_data)
    
    evaluation = CandidateEvaluation(
        candidate_name=eval_data['evaluation']['candidate_name'],
        candidate_email=eval_data['evaluation']['candidate_email'],
        interview_date=eval_data['evaluation']['interview_date'],
        role=eval_data['evaluation']['role'],
        skill_scores=skill_scores,
        weighted_average=eval_data['evaluation']['weighted_average'],
        recommendation=eval_data['evaluation']['recommendation'],
        recommendation_label=eval_data['evaluation']['recommendation_label'],
        recommendation_description=eval_data['evaluation']['recommendation_description'],
        strengths=eval_data['evaluation']['strengths'],
        concerns=eval_data['evaluation']['concerns'],
        overall_summary=eval_data['evaluation']['overall_summary'],
        recommended_for_followup=eval_data['evaluation']['recommended_for_followup'],
        followup_focus_areas=eval_data['evaluation']['followup_focus_areas'],
        followup_questions=eval_data['evaluation']['followup_questions']
    )
    
    try:
        opening, followup_session = followup_engine.start_followup_session(
            followup_session_id,
            evaluation,
            eval_data['session_data'].get('conversation_history', [])
        )
        
        session['followup_session_id'] = followup_session_id
        
        return jsonify({
            "success": True,
            "message": opening,
            "session_id": followup_session_id
        })
    except Exception as e:
        print(f"Error starting follow-up: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/admin/followup/respond', methods=['POST'])
@admin_required
def process_followup_response():
    """Process a response in follow-up interview"""
    if not AI_ENABLED:
        return jsonify({"success": False, "error": "AI features not available"}), 503
    
    data = request.get_json()
    response_text = data.get('response', '').strip()
    followup_session_id = session.get('followup_session_id')
    
    if not response_text:
        return jsonify({"success": False, "error": "Please provide an answer"})
    
    if not followup_session_id:
        return jsonify({"success": False, "error": "No active follow-up session"})
    
    try:
        ai_response, followup_session = followup_engine.process_followup_response(
            followup_session_id, 
            response_text
        )
        
        return jsonify({
            "success": True,
            "message": ai_response
        })
    except Exception as e:
        print(f"Error in follow-up: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# API ROUTES - DATA EXPORT
# =============================================================================

@app.route('/api/admin/evaluations', methods=['GET'])
@admin_required
def get_all_evaluations():
    """Get all evaluations as JSON"""
    return jsonify({
        "evaluations": [
            {
                "session_id": sid,
                "evaluation": data['evaluation'],
                "timestamp": data['timestamp']
            }
            for sid, data in completed_evaluations.items()
        ]
    })


@app.route('/api/admin/evaluation/<session_id>/export', methods=['GET'])
@admin_required
def export_evaluation(session_id):
    """Export full evaluation data"""
    data = completed_evaluations.get(session_id)
    if not data:
        return jsonify({"error": "Not found"}), 404
    
    return jsonify(data)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)
