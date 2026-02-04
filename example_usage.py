"""
Example usage of the Interview Chatbot with advanced features
"""

from interview_chatbot import InterviewChatbot
import json

def example_automated_interview():
    """
    Example: Run an automated interview with pre-filled responses
    (useful for testing)
    """
    print("Example 1: Automated Interview Test\n")
    
    bot = InterviewChatbot()
    
    # Sample responses for testing
    test_responses = [
        "Sarah Johnson",
        "I'm currently in Philadelphia and available to work locally.",
        "I graduated with a degree in Marketing last year and completed two internships. During my internship at a local agency, I managed social media accounts and helped with email campaigns. I also ran the social media for my university's business club, growing our Instagram following by 300% in one semester.",
        "I'm very comfortable with social media platforms, especially Instagram, Facebook, LinkedIn, and TikTok. I've also worked with email marketing through Mailchimp and have basic knowledge of Google Analytics and Google Ads. I'm eager to learn more about SEO and paid advertising.",
        "I've created various content types including social media posts (graphics and captions), blog articles for company websites, email newsletters, and short-form videos for Instagram Reels and TikTok. I use Canva for design and have basic video editing skills.",
        "I use Canva for design, Hootsuite for social media scheduling, Mailchimp for email marketing, Google Analytics for tracking website performance, and I'm familiar with the Meta Business Suite for Facebook and Instagram ads.",
        "At my internship, I led a back-to-school campaign for a local retail client. I created a content calendar, designed graphics, wrote copy, and scheduled posts across three platforms. We also ran a giveaway that increased engagement by 45% and brought in 200 new followers in two weeks. The campaign resulted in a 20% increase in store traffic during the promotion period.",
        "My strongest skills are content creation and social media management. I'm creative, detail-oriented, and good at writing engaging copy. I'm most excited to develop my skills in paid advertising, data analysis, and campaign strategy. I want to better understand how to measure ROI and optimize campaigns based on data.",
        "In my university business club, I worked with a team of five to organize a marketing conference. I handled all promotional materials while others managed logistics and sponsorships. We had weekly meetings where I presented our social media metrics and adjusted our strategy based on what was working. Clear communication and being open to feedback helped us sell out the event.",
        "I'm really interested in Nytro's focus on digital campaigns and the opportunity to work on diverse US projects. As a junior marketer, I want to learn from experienced professionals and work somewhere that values creativity and data-driven decision-making. The variety of work and the collaborative environment really appeal to me.",
        "I'm available to start immediately, or can provide two weeks' notice to my current part-time position if needed.",
        "Yes! I'd love to know more about the team structure and who I'd be working with directly. Also, what does success look like in this role after the first 6 months? And are there opportunities for professional development or training?"
    ]
    
    for response in test_responses:
        result = bot.process_response(response)
        if result["status"] == "complete":
            print(result["message"])
            break
    
    # Save and return
    filepath = bot.save_interview("example_interview.json")
    print(f"\nTest interview saved to: {filepath}\n")
    
    return bot


def example_with_scoring():
    """
    Example: Interview with basic scoring system
    """
    print("\nExample 2: Interview with Scoring\n")
    
    class ScoringInterviewBot(InterviewChatbot):
        def __init__(self):
            super().__init__()
            self.scores = {}
        
        def score_response(self, question_id: str, response: str) -> dict:
            """Simple keyword-based scoring"""
            score = 3  # Default score
            feedback = []
            
            # Scoring criteria by question type
            scoring_keywords = {
                "digital_campaigns": {
                    "excellent": ["analytics", "seo", "sem", "social media", "email"],
                    "good": ["facebook", "instagram", "google"],
                },
                "content_experience": {
                    "excellent": ["writing", "design", "video", "graphics", "blog"],
                    "good": ["content", "social", "posts"],
                },
                "tools": {
                    "excellent": ["analytics", "crm", "automation", "adobe"],
                    "good": ["canva", "mailchimp", "hootsuite"],
                }
            }
            
            response_lower = response.lower()
            
            if question_id in scoring_keywords:
                excellent_matches = sum(1 for kw in scoring_keywords[question_id].get("excellent", []) 
                                       if kw in response_lower)
                good_matches = sum(1 for kw in scoring_keywords[question_id].get("good", []) 
                                  if kw in response_lower)
                
                if excellent_matches >= 3:
                    score = 5
                    feedback.append("Strong technical knowledge demonstrated")
                elif excellent_matches >= 2 or good_matches >= 3:
                    score = 4
                    feedback.append("Good familiarity with relevant tools/concepts")
                elif good_matches >= 1:
                    score = 3
                    feedback.append("Basic knowledge present")
                else:
                    score = 2
                    feedback.append("Limited technical detail provided")
            
            # Check response length
            word_count = len(response.split())
            if word_count < 10:
                score = max(1, score - 1)
                feedback.append("Response could be more detailed")
            elif word_count > 50:
                feedback.append("Thorough and detailed response")
            
            return {
                "score": score,
                "feedback": feedback,
                "word_count": word_count
            }
        
        def process_response(self, response: str):
            result = super().process_response(response)
            
            # Score the response
            if self.current_question > 0:  # Don't score the name question
                prev_question_id = self.questions[self.current_question - 1]["id"]
                if prev_question_id in ["digital_campaigns", "content_experience", "tools"]:
                    score_data = self.score_response(prev_question_id, response)
                    self.scores[prev_question_id] = score_data
                    print(f"\n[Auto-scored: {score_data['score']}/5]")
            
            return result
        
        def get_final_score(self) -> dict:
            """Calculate overall interview score"""
            if not self.scores:
                return {"overall_score": 0, "assessment": "No scores available"}
            
            avg_score = sum(s["score"] for s in self.scores.values()) / len(self.scores)
            
            if avg_score >= 4.5:
                assessment = "Excellent candidate - strong recommend"
            elif avg_score >= 3.5:
                assessment = "Good candidate - recommend for next round"
            elif avg_score >= 2.5:
                assessment = "Moderate candidate - consider with reservations"
            else:
                assessment = "Weak candidate - not recommended"
            
            return {
                "overall_score": round(avg_score, 2),
                "assessment": assessment,
                "individual_scores": self.scores
            }
    
    # This would be used in an actual interview
    print("Scoring bot created. Would score responses in real-time during interview.")
    print("Example score output: [Auto-scored: 4/5]")
    
    return ScoringInterviewBot()


def example_export_for_review():
    """
    Example: Export interview in human-readable format for review
    """
    print("\nExample 3: Export for Review\n")
    
    # Load the example interview
    with open('/home/claude/example_interview.json', 'r') as f:
        interview_data = json.load(f)
    
    # Create formatted review document
    review_doc = f"""
INTERVIEW REVIEW DOCUMENT
========================

Candidate: {interview_data['candidate_name']}
Position: {interview_data['position']}
Company: {interview_data['company']}
Interview Date: {interview_data['interview_date']}

RESPONSES
=========

"""
    
    # Group responses by category
    categories = {}
    for q_id, data in interview_data['responses'].items():
        # Find category from original questions
        bot = InterviewChatbot()
        category = next((q['category'] for q in bot.questions if q['id'] == q_id), 'other')
        
        if category not in categories:
            categories[category] = []
        
        categories[category].append({
            'question': data['question'],
            'answer': data['answer']
        })
    
    # Format by category
    for category, items in categories.items():
        review_doc += f"\n{category.upper()}\n"
        review_doc += "-" * len(category) + "\n\n"
        
        for item in items:
            review_doc += f"Q: {item['question']}\n"
            review_doc += f"A: {item['answer']}\n\n"
    
    review_doc += """
INTERVIEWER NOTES
================

Overall Impression: [To be filled by reviewer]

Strengths:
- 
- 
- 

Areas of Concern:
- 
- 

Recommendation: [ ] Advance to next round  [ ] Reject  [ ] Maybe

Additional Comments:


"""
    
    # Save review document
    with open('/home/claude/interview_review.txt', 'w') as f:
        f.write(review_doc)
    
    print("Review document created: interview_review.txt")
    print("\nPreview:")
    print(review_doc[:500] + "...\n")


if __name__ == "__main__":
    print("="*60)
    print("INTERVIEW CHATBOT USAGE EXAMPLES")
    print("="*60 + "\n")
    
    # Run examples
    bot1 = example_automated_interview()
    bot2 = example_with_scoring()
    example_export_for_review()
    
    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60)
