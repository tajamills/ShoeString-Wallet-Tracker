"""
AI Support Agent Service
Provides AI-powered help for cryptocurrency tax questions and app usage.
Uses OpenAI GPT for intelligent responses.
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

# System prompt for the support agent
SUPPORT_AGENT_SYSTEM_PROMPT = """You are a helpful AI support assistant for Crypto Bag Tracker, a cryptocurrency tax tracking and chain of custody analysis application.

Your expertise includes:
1. **Cryptocurrency Tax Basics**
   - Capital gains (short-term vs long-term)
   - Cost basis calculation methods (FIFO, LIFO, HIFO)
   - Taxable events (selling, trading, spending crypto)
   - Non-taxable events (transfers between own wallets, gifts under threshold)
   - IRS Form 8949 and Schedule D

2. **App Features**
   - Wallet analysis across 12+ blockchains
   - Chain of Custody analysis for tracing asset origins
   - Exchange integration (Coinbase, Binance, Kraken, etc.)
   - CSV import/export for tax reporting
   - Form 8949 generation

3. **Common User Questions**
   - How to connect exchanges
   - Understanding cost basis
   - Why transfers shouldn't be taxed
   - How to handle DeFi transactions
   - Understanding the chain of custody feature

Guidelines:
- Be concise but thorough
- Use simple language, avoid jargon when possible
- If you're unsure, say so and suggest contacting support@cryptobagtracker.io
- For legal/tax advice, recommend consulting a tax professional
- Be friendly and helpful

Note: You are NOT a tax advisor. Always recommend users consult with a qualified tax professional for specific tax advice."""


class SupportAgentService:
    """
    AI-powered support agent for answering user questions.
    """
    
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY', '')
        self.conversations: Dict[str, List[Dict]] = {}
    
    async def get_response(
        self,
        user_id: str,
        message: str,
        conversation_history: List[Dict] = None
    ) -> Dict:
        """
        Get AI response to a user message.
        
        Args:
            user_id: User ID for session tracking
            message: User's question
            conversation_history: Previous messages for context
            
        Returns:
            Dict with response and updated conversation
        """
        if not self.api_key:
            return {
                "success": False,
                "response": "AI support is not configured. Please contact support@cryptobagtracker.io",
                "error": "API key not set"
            }
        
        try:
            # Initialize chat with session
            session_id = f"support_{user_id}_{datetime.utcnow().strftime('%Y%m%d')}"
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=SUPPORT_AGENT_SYSTEM_PROMPT
            ).with_model("openai", "gpt-4o")
            
            # Add conversation history context if provided
            context_text = ""
            if conversation_history:
                context_text = "Previous conversation:\n"
                for msg in conversation_history[-5:]:  # Last 5 messages
                    role = "User" if msg.get('role') == 'user' else "Assistant"
                    context_text += f"{role}: {msg.get('content', '')}\n"
                context_text += "\nCurrent question:\n"
            
            # Create user message
            user_message = UserMessage(
                text=context_text + message if context_text else message
            )
            
            # Get response
            response = await chat.send_message(user_message)
            
            return {
                "success": True,
                "response": response,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Support agent error: {str(e)}")
            return {
                "success": False,
                "response": "I'm having trouble processing your request. Please try again or contact support@cryptobagtracker.io",
                "error": str(e)
            }
    
    def get_suggested_questions(self) -> List[str]:
        """Get list of suggested questions for users."""
        return [
            "How do I calculate my crypto capital gains?",
            "What's the difference between short-term and long-term gains?",
            "How do I import my Coinbase transactions?",
            "What is chain of custody analysis?",
            "Why is my cost basis showing as zero?",
            "How do wallet transfers affect my taxes?",
            "What is FIFO and how does it work?",
            "How do I generate Form 8949?",
            "Can I connect multiple exchanges?",
            "What blockchains are supported?"
        ]


# Global service instance
support_agent_service = SupportAgentService()
