"""
Nytro Junior Marketer Interview Chatbot
Conducts first-round interviews for Junior Marketer position
"""

import json
from datetime import datetime
from typing import Dict, List, Optional

class InterviewChatbot:
    def __init__(self):
        self.candidate_name = ""
        self.responses = {}
        self.current_question = 0
        
        # Interview questions structure
        self.questions = [
            {
                "id": "intro",
                "question": "Hi! I'm the Nytro hiring assistant. I'll be conducting your initial interview for the Junior Marketer position. This should take about 15-20 minutes. Let's start with your name?",
                "type": "text",
                "category": "introduction"
            },
            {
                "id": "location",
                "question": "Great to meet you, {name}! This position is based in the Philadelphia area. Can you confirm your current location and whether you're able to work in or relocate to the Philadelphia area?",
                "type": "text",
                "category": "logistics"
            },
            {
                "id": "background",
                "question": "Tell me a bit about your background in marketing. What experience do you have, even if it's from internships, coursework, or personal projects?",
                "type": "long_text",
                "category": "experience"
            },
            {
                "id": "digital_campaigns",
                "question": "This role involves working on digital campaigns. What digital marketing channels or platforms are you familiar with? (e.g., social media, email marketing, Google Ads, SEO, etc.)",
                "type": "long_text",
                "category": "skills"
            },
            {
                "id": "content_experience",
                "question": "Content creation is a key part of this role. Can you describe any experience you have creating marketing content? This could include writing, design, video, or other formats.",
                "type": "long_text",
                "category": "skills"
            },
            {
                "id": "tools",
                "question": "What marketing tools or software are you comfortable using? (e.g., social media management tools, email platforms, analytics tools, design software, etc.)",
                "type": "text",
                "category": "technical"
            },
            {
                "id": "campaign_example",
                "question": "Can you walk me through a marketing project or campaign you've worked on? What was your role, and what were the results?",
                "type": "long_text",
                "category": "experience"
            },
            {
                "id": "strengths",
                "question": "What do you consider your strongest marketing skills? What areas are you most excited to develop further?",
                "type": "long_text",
                "category": "self_assessment"
            },
            {
                "id": "teamwork",
                "question": "This role involves day-to-day marketing execution as part of a team. Tell me about a time you collaborated with others on a project. What was your approach?",
                "type": "long_text",
                "category": "soft_skills"
            },
            {
                "id": "why_nytro",
                "question": "What interests you about this Junior Marketer position at Nytro?",
                "type": "long_text",
                "category": "motivation"
            },
            {
                "id": "availability",
                "question": "When would you be available to start if offered the position?",
                "type": "text",
                "category": "logistics"
            },
            {
                "id": "questions",
                "question": "Do you have any questions for us about the role, team, or company?",
                "type": "long_text",
                "category": "closing"
            }
        ]
    
    def get_current_question(self) -> str:
        """Get the current question text, with name substitution if needed"""
        if self.current_question >= len(self.questions):
            return None
        
        question_data = self.questions[self.current_question]
        question = question_data["question"]
        
        # Substitute candidate name if placeholder exists
        if "{name}" in question:
            question = question.replace("{name}", self.candidate_name)
        
        return question
    
    def process_response(self, response: str) -> Dict:
        """Process candidate's response and move to next question"""
        if self.current_question >= len(self.questions):
            return {"status": "complete", "message": "Interview completed"}
        
        question_id = self.questions[self.current_question]["id"]
        
        # Store response
        self.responses[question_id] = {
            "question": self.questions[self.current_question]["question"],
            "answer": response,
            "timestamp": datetime.now().isoformat()
        }
        
        # Special handling for name question
        if question_id == "intro":
            self.candidate_name = response.strip()
        
        # Move to next question
        self.current_question += 1
        
        # Check if interview is complete
        if self.current_question >= len(self.questions):
            return {
                "status": "complete",
                "message": self.get_completion_message()
            }
        
        return {
            "status": "continue",
            "next_question": self.get_current_question()
        }
    
    def get_completion_message(self) -> str:
        """Generate completion message"""
        return f"""
Thank you for completing the interview, {self.candidate_name}! 

Your responses have been recorded. Our hiring team will review your interview and get back to you within 5-7 business days regarding next steps.

We appreciate your time and interest in the Junior Marketer position at Nytro!

If you have any questions in the meantime, feel free to reach out to our HR team.

Best of luck!
"""
    
    def save_interview(self, filename: Optional[str] = None) -> str:
        """Save interview responses to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"interview_{self.candidate_name.replace(' ', '_')}_{timestamp}.json"
        
        interview_data = {
            "candidate_name": self.candidate_name,
            "interview_date": datetime.now().isoformat(),
            "position": "Junior Marketer",
            "company": "Nytro",
            "responses": self.responses,
            "status": "completed" if self.current_question >= len(self.questions) else "incomplete"
        }
        
        # Use filename as-is if it's already a full path, otherwise prepend /home/claude/
        if filename.startswith('/'):
            filepath = filename
        else:
            filepath = f"/home/claude/{filename}"
        
        with open(filepath, 'w') as f:
            json.dump(interview_data, f, indent=2)
        
        return filepath
    
    def get_summary(self) -> str:
        """Generate a summary of the interview"""
        if not self.responses:
            return "No responses recorded yet."
        
        summary = f"Interview Summary for {self.candidate_name}\n"
        summary += "=" * 50 + "\n\n"
        
        for q_id, data in self.responses.items():
            summary += f"Q: {data['question']}\n"
            summary += f"A: {data['answer']}\n\n"
        
        return summary


def run_interview():
    """Main function to run the interview"""
    print("\n" + "="*60)
    print("NYTRO JUNIOR MARKETER INTERVIEW")
    print("="*60 + "\n")
    
    bot = InterviewChatbot()
    
    # Start interview
    print(bot.get_current_question())
    
    while bot.current_question < len(bot.questions):
        print("\nYour answer: ", end="")
        response = input().strip()
        
        if not response:
            print("Please provide an answer to continue.")
            continue
        
        result = bot.process_response(response)
        
        if result["status"] == "complete":
            print("\n" + result["message"])
            break
        else:
            print("\n" + result["next_question"])
    
    # Save interview
    print("\nSaving interview responses...")
    filepath = bot.save_interview()
    print(f"Interview saved to: {filepath}")
    
    # Ask if they want to see summary
    print("\nWould you like to see a summary of your responses? (yes/no): ", end="")
    show_summary = input().strip().lower()
    
    if show_summary in ['yes', 'y']:
        print("\n" + bot.get_summary())
    
    return bot


if __name__ == "__main__":
    interview_bot = run_interview()
