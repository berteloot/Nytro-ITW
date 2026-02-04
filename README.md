# Nytro AI Interview Chatbot

An intelligent, AI-powered interview chatbot that conducts first-round candidate screening with adaptive questioning, structured evaluation, and follow-up interview support.

## Features

### AI-Powered Conversations
- **Adaptive Questioning**: The AI dynamically generates follow-up questions based on candidate responses
- **Natural Dialogue**: Conversational interview style that puts candidates at ease
- **Context-Aware**: Remembers earlier responses and builds on them throughout the interview

### Structured Evaluation
- **Skills Assessment**: Evaluates candidates against defined competencies with 1-5 scoring
- **Weighted Scoring**: Skills are weighted by importance for accurate overall assessment
- **Evidence-Based**: Scores include specific quotes and observations from the interview

### Recommendation System
- **Strong Yes**: Score ≥ 4.0 - Fast-track to final interview
- **Yes**: Score ≥ 3.2 - Recommend for follow-up
- **Maybe**: Score ≥ 2.5 - Needs further evaluation
- **No**: Score < 2.5 - Do not proceed

### Follow-Up Interview Support
- **AI-Generated Guide**: Detailed guide for human interviewers with focus areas
- **Suggested Questions**: Targeted questions based on initial interview gaps
- **AI-Assisted Follow-up**: Option to conduct AI-powered follow-up interviews

### Admin Dashboard
- View all completed interviews and evaluations
- Detailed skill breakdowns with evidence
- Full interview transcripts
- Export evaluation data to JSON
- Download follow-up interview guides

### HubSpot Integration
- Automatic contact creation/lookup
- Interview evaluation saved as notes
- Seamless CRM integration

## Quick Start

### Prerequisites
- Python 3.8+
- OpenAI API key
- (Optional) HubSpot Private App token

### Installation

```bash
# Clone the repository
cd nytro-interview-chatbot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Set environment variables:

```bash
# Required
export OPENAI_API_KEY="your-openai-api-key"

# Optional
export HUBSPOT_ACCESS_TOKEN="your-hubspot-token"
export ADMIN_PASSWORD="your-admin-password"
export SECRET_KEY="your-flask-secret-key"
```

### Run the Application

```bash
# Development
python app.py

# Production
gunicorn app:app
```

Visit:
- **Interview**: http://localhost:5000
- **Admin Dashboard**: http://localhost:5000/admin

## Customizing the Interview

All interview parameters are configured in `interview_guidelines.yaml`:

### Skills & Competencies

```yaml
skills:
  digital_marketing_knowledge:
    name: "Digital Marketing Knowledge"
    description: "Understanding of digital marketing channels..."
    weight: 5  # Importance 1-5
    key_indicators:
      - "Can name specific platforms and their use cases"
      - "Understands paid vs organic marketing"
    red_flags:
      - "Cannot name any digital channels"
    example_questions:
      - "What digital marketing channels are you familiar with?"
```

### Scoring Rubric

```yaml
scoring_rubric:
  5:
    label: "Exceptional"
    description: "Exceeds expectations significantly"
    criteria:
      - "Provides specific, relevant examples with clear results"
```

### Recommendation Thresholds

```yaml
recommendations:
  strong_yes:
    min_weighted_score: 4.0
    label: "Strong Yes - Proceed to Final Interview"
```

### AI Behavior

```yaml
interview:
  personality:
    name: "Nytro Hiring Assistant"
    tone: "professional yet friendly"
    guidelines:
      - "Ask one question at a time"
      - "Probe deeper on vague answers"

ai_config:
  model: "gpt-4o"
  temperature: 0.7
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Flask Web App                            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   Candidate  │  │    Admin     │  │   Follow-up  │       │
│  │  Interview   │  │  Dashboard   │  │   Interview  │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │               │
│         └────────────┬────┴────────────────┘               │
│                      │                                      │
│              ┌───────▼────────┐                             │
│              │   AI Interview │                             │
│              │     Engine     │                             │
│              └───────┬────────┘                             │
│                      │                                      │
│    ┌─────────────────┼─────────────────┐                   │
│    │                 │                 │                    │
│    ▼                 ▼                 ▼                    │
│ ┌──────┐      ┌──────────┐      ┌──────────┐              │
│ │OpenAI│      │Guidelines│      │ HubSpot  │              │
│ │ API  │      │  YAML    │      │   API    │              │
│ └──────┘      └──────────┘      └──────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## API Endpoints

### Candidate Interview
- `POST /api/start` - Start new interview session
- `POST /api/respond` - Submit response, get next question
- `GET /api/progress` - Get interview progress

### Admin (Requires Authentication)
- `GET /admin` - Dashboard
- `GET /admin/evaluation/<id>` - View evaluation details
- `GET /admin/evaluation/<id>/followup-guide` - Get follow-up guide
- `POST /api/admin/followup/start` - Start follow-up interview
- `POST /api/admin/followup/respond` - Process follow-up response

## Best Practices Implemented

Based on research from Indeed x OpenAI, Google's structured interviewing, and AI hiring best practices:

1. **Human-in-the-Loop**: AI screens, humans make final decisions
2. **Structured Evaluation**: Consistent rubrics prevent bias
3. **Evidence-Based Scoring**: Every score backed by specific observations
4. **Adaptive Questioning**: Follows up on vague or strong responses
5. **Transparency**: Clear criteria defined upfront
6. **Follow-up Support**: Helps human interviewers focus on key areas

## Files Overview

| File | Purpose |
|------|---------|
| `app.py` | Flask application with all routes |
| `ai_interview_engine.py` | AI engine with OpenAI integration |
| `interview_guidelines.yaml` | All interview configuration |
| `templates/` | HTML templates for UI |
| `static/` | CSS and JavaScript |

## Deployment

### Render

The app is configured for Render deployment with `render.yaml`:

```yaml
services:
  - type: web
    name: nytro-interview
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: OPENAI_API_KEY
        sync: false
      - key: HUBSPOT_ACCESS_TOKEN
        sync: false
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4 |
| `HUBSPOT_ACCESS_TOKEN` | No | HubSpot Private App token |
| `ADMIN_PASSWORD` | No | Admin dashboard password (default: nytro-admin-2024) |
| `SECRET_KEY` | No | Flask session secret |
| `PORT` | No | Server port (default: 5000) |

## Security Notes

- Change `ADMIN_PASSWORD` in production
- Set a strong `SECRET_KEY` for session security
- Use HTTPS in production
- Consider rate limiting for public endpoints
- Review HubSpot API permissions

## License

Customize as needed for your hiring process.
