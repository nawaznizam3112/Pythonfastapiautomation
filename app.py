import os
from typing import Literal
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Real Estate Speed-to-Lead Engine")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 1. Input Schema: What your website form or webhook sends to FastAPI
class IncomingLead(BaseModel):
    full_name: str = Field(..., example="Rahul Sharma")
    email: str = Field(..., example="rahul.sharma@example.com")
    phone: str = Field(..., example="+919876543210")
    inquiry_message: str = Field(
        ..., 
        example="Looking for a 3BHK villa in whitefield area. Budget is around 2.5 Cr. Want to close within 30 days."
    )

# 2. Output Schema: Forces the AI to return exact, structured fields
class LeadAnalysis(BaseModel):
    lead_score: int = Field(..., description="Score from 1 to 10 based on buying intent, budget clarity, and timeline.")
    intent_type: Literal["Buyer", "Seller", "Renter", "Investor", "Unclear"]
    urgency: Literal["High", "Medium", "Low"]
    extracted_budget: str = Field(..., description="Estimated budget mentioned, or 'Not specified'")
    preferred_location: str = Field(..., description="Target neighborhood or city, or 'Not specified'")
    summary_for_agent: str = Field(..., description="A 2-bullet summary for the real estate agent.")
    instant_email_reply: str = Field(..., description="A warm, personalized email reply inviting them to book a call.")

# 3. Background Task: Runs email/Slack alerts without making the webhook wait
def trigger_instant_actions(lead: IncomingLead, analysis: LeadAnalysis):
    print("\n--- TRIGGERING AUTOMATIONS ---")
    print(f"1. [EMAIL SENT] To: {lead.email}")
    print(f"   Body: {analysis.instant_email_reply}\n")
    
    if analysis.lead_score >= 8:
        print(f"2. [URGENT AGENT ALERT] Hot Lead ({analysis.lead_score}/10): {lead.full_name} ({lead.phone})")
        print(f"   Summary: {analysis.summary_for_agent}")
    print("------------------------------\n")

# 4. The Webhook Endpoint
@app.post("/webhook/new-lead")
async def process_new_lead(lead: IncomingLead, background_tasks: BackgroundTasks):
    try:
        system_prompt = (
            "You are an expert real estate sales assistant. Analyze incoming property inquiries. "
            "Score leads higher (8-10) if they state a clear budget, specific location, and immediate timeline (under 60 days). "
            "Draft a helpful, non-pushy email reply from 'Apex Realty Group'."
        )

        # Call OpenAI with Pydantic Structured Outputs
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Name: {lead.full_name}\nMessage: {lead.inquiry_message}"}
            ],
            response_format=LeadAnalysis,
        )

        analysis_result = completion.choices[0].message.parsed

        # Queue the email & alert tasks in the background
        background_tasks.add_task(trigger_instant_actions, lead, analysis_result)

        return {
            "status": "success",
            "lead_name": lead.full_name,
            "analysis": analysis_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
