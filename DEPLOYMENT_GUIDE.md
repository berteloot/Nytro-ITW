# Nytro Interview Chatbot - Render Deployment Guide

This guide walks you through deploying the interview chatbot to Render with HubSpot integration.

## Project Structure

```
nytro-interview-chatbot/
├── app.py                 # Flask application
├── requirements.txt       # Python dependencies
├── render.yaml           # Render deployment config
├── templates/
│   └── index.html        # Frontend HTML
└── static/
    ├── style.css         # Styles
    └── app.js            # Frontend JavaScript
```

## Step 1: Set Up HubSpot Private App

Create a Private App in HubSpot to get an Access Token.

### Create a Private App

1. Log in to your HubSpot account
2. Go to **Settings** (gear icon) > **Integrations** > **Private Apps**
3. Click **Create a private app**
4. Give it a name (e.g., "Nytro Interview Chatbot")
5. Go to the **Scopes** tab and enable these permissions:
   - `crm.objects.contacts.read`
   - `crm.objects.contacts.write`
   - `crm.objects.notes.read` (if available, otherwise skip)
   - `crm.objects.notes.write` (if available, otherwise skip)
6. Click **Create app**
7. Copy the **Access Token** - you'll need this for deployment

### What the App Does in HubSpot

When a candidate completes an interview:
1. Searches for existing contact by email
2. Creates a new contact if not found (with name, email, city)
3. Creates a Note attached to the contact with all interview responses
4. The Note appears in the contact's timeline in HubSpot

## Step 2: Push to GitHub

1. Create a new GitHub repository
2. Push all files:
   ```bash
   git init
   git add .
   git commit -m "Initial commit - Nytro Interview Chatbot"
   git remote add origin https://github.com/YOUR_USERNAME/nytro-interview-chatbot.git
   git push -u origin main
   ```

## Step 3: Deploy to Render

### Option A: Deploy with Blueprint (Recommended)

1. Go to [render.com](https://render.com) and sign in
2. Click **New** > **Blueprint**
3. Connect your GitHub repository
4. Render will detect `render.yaml` and configure automatically
5. Add your environment variables when prompted

### Option B: Manual Deployment

1. Go to [render.com](https://render.com) and sign in
2. Click **New** > **Web Service**
3. Connect your GitHub repository
4. Configure:
   - **Name**: `nytro-interview-chatbot`
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`

## Step 4: Configure Environment Variables

In Render dashboard, go to your service > **Environment** and add:

| Variable | Description | Required |
|----------|-------------|----------|
| `SECRET_KEY` | Flask session secret (auto-generated if using Blueprint) | Yes |
| `HUBSPOT_ACCESS_TOKEN` | Your HubSpot Private App access token | Yes |

## Step 5: Test Your Deployment

1. Once deployed, Render provides a URL like `https://nytro-interview-chatbot.onrender.com`
2. Visit the URL to test the chatbot
3. Complete a test interview
4. Check HubSpot:
   - Go to **Contacts** and find the test contact
   - Open the contact and check the **Notes** in the timeline
   - You should see the interview responses formatted nicely

## Local Development

### Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export SECRET_KEY="dev-secret-key"
export HUBSPOT_ACCESS_TOKEN="your-private-app-token"
export FLASK_ENV=development

# Run the app
python app.py
```

Visit `http://localhost:5000` to test locally.

### Test Without HubSpot

The app works without HubSpot configuration - responses just won't be submitted. Useful for UI testing.

## How It Works

### Interview Flow

1. Candidate visits the chatbot URL
2. Clicks "Start Interview"
3. Answers 13 questions covering:
   - Name and email
   - Location/relocation
   - Marketing background
   - Digital marketing experience
   - Content creation skills
   - Tools knowledge
   - Campaign examples
   - Strengths and growth areas
   - Teamwork experience
   - Interest in Nytro
   - Availability
   - Questions for the team
4. On completion, data is sent to HubSpot

### HubSpot Integration

When interview completes:
1. **Search Contact**: Looks for existing contact by email
2. **Create Contact**: If not found, creates new contact with:
   - First name / Last name (parsed from full name)
   - Email address
   - City (from location answer)
3. **Create Note**: Attaches a formatted HTML note containing:
   - Interview date and position
   - All questions and answers
   - Source attribution

## Customization

### Modify Questions

Edit the `QUESTIONS` list in `app.py`:

```python
{
    "id": "unique_id",
    "question": "Your question here?",
    "type": "text",  # or "long_text" or "email"
    "category": "category_name"
}
```

Also update `QUESTION_LABELS` for the note formatting.

### Change Branding

Edit `templates/index.html` and `static/style.css`:
- Update logo and colors in CSS variables
- Modify the header and welcome screen text

### Customize Note Format

Edit the `format_interview_note()` function in `app.py` to change how interview responses appear in HubSpot.

## Troubleshooting

### HubSpot Not Receiving Data

1. Check `HUBSPOT_ACCESS_TOKEN` is set correctly
2. Verify Private App has required scopes
3. Check Render logs: **Logs** tab in your service
4. Test the token with a simple curl:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" \
     https://api.hubapi.com/crm/v3/objects/contacts?limit=1
   ```

### Contact Created But No Note

1. Private App may need additional scopes
2. Check logs for "Error creating note" messages
3. Verify the association type ID (202 for Note to Contact)

### Session Issues

If interviews aren't persisting:
1. Ensure `SECRET_KEY` is set
2. Check browser allows cookies
3. Try clearing cookies and restarting

### Deployment Fails

1. Check `requirements.txt` has all dependencies
2. Verify Python version compatibility
3. Check Render build logs for specific errors

## Health Check

The app includes a health endpoint at `/health` that Render uses to monitor the service.

## HubSpot Private App Scopes Reference

Minimum required scopes:
- `crm.objects.contacts.read` - Search for existing contacts
- `crm.objects.contacts.write` - Create new contacts

For notes (engagement):
- The Notes API uses standard CRM scopes
- If notes aren't working, try adding `crm.objects.custom.read` and `crm.objects.custom.write`

## Cost

**Render** free tier includes:
- 750 hours/month of web service runtime
- Auto-sleep after 15 minutes of inactivity
- Automatic HTTPS

**HubSpot** Private Apps are free on all plans including the free CRM.
