"""Support routes - AI chat, contact form, conversation history"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict
from datetime import datetime, timezone
import uuid
import logging

from .dependencies import db, get_current_user
from .models import SupportMessageRequest, ContactRequest
from support_agent_service import support_agent_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/support", tags=["Support"])


@router.post("/ai-chat")
async def ai_support_chat(
    request: SupportMessageRequest,
    user: dict = Depends(get_current_user)
):
    """Get AI-powered support response"""
    try:
        result = await support_agent_service.get_response(
            user_id=user.get("id", "anonymous"),
            message=request.message,
            conversation_history=request.conversation_history
        )
        
        await db.support_conversations.update_one(
            {"user_id": user["id"], "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
            {
                "$push": {
                    "messages": {
                        "role": "user",
                        "content": request.message,
                        "timestamp": datetime.now(timezone.utc)
                    }
                },
                "$set": {"updated_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )
        
        if result.get("success"):
            await db.support_conversations.update_one(
                {"user_id": user["id"], "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
                {
                    "$push": {
                        "messages": {
                            "role": "assistant",
                            "content": result["response"],
                            "timestamp": datetime.now(timezone.utc)
                        }
                    }
                }
            )
        
        return result
        
    except Exception as e:
        logger.error(f"AI support error: {str(e)}")
        return {
            "success": False,
            "response": "Unable to process your request. Please try again or email support@cryptobagtracker.io"
        }


@router.get("/suggested-questions")
async def get_suggested_questions():
    """Get suggested questions for the support chat"""
    return {
        "questions": support_agent_service.get_suggested_questions()
    }


@router.post("/contact")
async def submit_contact_form(request: ContactRequest):
    """Submit a contact form message"""
    try:
        contact_record = {
            "id": str(uuid.uuid4()),
            "name": request.name,
            "email": request.email,
            "subject": request.subject,
            "message": request.message,
            "status": "new",
            "created_at": datetime.now(timezone.utc),
            "responded_at": None
        }
        
        await db.contact_messages.insert_one(contact_record)
        
        logger.info(f"New contact form submission from {request.email}")
        
        return {
            "success": True,
            "message": "Thank you for your message! We'll get back to you within 24-48 hours.",
            "ticket_id": contact_record["id"]
        }
        
    except Exception as e:
        logger.error(f"Contact form error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit contact form")


@router.get("/conversation-history")
async def get_conversation_history(user: dict = Depends(get_current_user)):
    """Get user's support conversation history"""
    try:
        conversations = await db.support_conversations.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("updated_at", -1).limit(10).to_list(10)
        
        return {"conversations": conversations}
        
    except Exception as e:
        logger.error(f"Error fetching conversation history: {str(e)}")
        return {"conversations": []}
