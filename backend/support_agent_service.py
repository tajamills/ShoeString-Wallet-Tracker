"""
AI Support Agent Service
Provides AI-powered help for cryptocurrency tax questions and app usage.
Uses OpenAI GPT for intelligent responses.
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import emergentintegrations, fall back to direct OpenAI if not available
try:
    from emergentintegrations.llm.chat import LlmChat, UserMessage
    EMERGENT_AVAILABLE = True
except ImportError:
    EMERGENT_AVAILABLE = False
    logger.warning("emergentintegrations not available, using fallback")
    try:
        import openai
        OPENAI_AVAILABLE = True
    except ImportError:
        OPENAI_AVAILABLE = False

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
        self.api_key = os.environ.get('EMERGENT_LLM_KEY', '') or os.environ.get('OPENAI_API_KEY', '')
        self.conversations: Dict[str, List[Dict]] = {}
    
    async def get_response(
        self,
        user_id: str,
        message: str,
        conversation_history: List[Dict] = None
    ) -> Dict:
        """
        Get AI response to a user message.
        """
        if not self.api_key:
            return {
                "success": False,
                "response": "AI support is not configured. Please contact support@cryptobagtracker.io",
                "error": "API key not set"
            }
        
        try:
            session_id = f"support_{user_id}_{datetime.utcnow().strftime('%Y%m%d')}"
            
            # Build context from conversation history
            context_text = ""
            if conversation_history:
                context_text = "Previous conversation:\n"
                for msg in conversation_history[-5:]:
                    role = "User" if msg.get('role') == 'user' else "Assistant"
                    context_text += f"{role}: {msg.get('content', '')}\n"
                context_text += "\nCurrent question:\n"
            
            full_message = context_text + message if context_text else message
            
            if EMERGENT_AVAILABLE:
                # Use emergentintegrations
                chat = LlmChat(
                    api_key=self.api_key,
                    session_id=session_id,
                    system_message=SUPPORT_AGENT_SYSTEM_PROMPT
                ).with_model("openai", "gpt-4o")
                
                user_message = UserMessage(text=full_message)
                response = await chat.send_message(user_message)
            
            elif OPENAI_AVAILABLE:
                # Fallback to direct OpenAI
                client = openai.AsyncOpenAI(api_key=self.api_key)
                completion = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": SUPPORT_AGENT_SYSTEM_PROMPT},
                        {"role": "user", "content": full_message}
                    ]
                )
                response = completion.choices[0].message.content
            
            else:
                # No AI available - return helpful fallback
                return {
                    "success": True,
                    "response": self._get_fallback_response(message),
                    "session_id": session_id,
                    "fallback": True
                }
            
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
    
    def _get_fallback_response(self, message: str) -> str:
        """Provide helpful response when AI is not available."""
        message_lower = message.lower()
        
        if "cost basis" in message_lower:
            return "Cost basis is the original value of an asset for tax purposes. We use FIFO (First-In, First-Out) method by default. For detailed help, please email support@cryptobagtracker.io"
        elif "capital gain" in message_lower:
            return "Capital gains are profits from selling crypto. Short-term (held <1 year) are taxed as ordinary income. Long-term (held >1 year) get preferential rates. For specific advice, consult a tax professional."
        elif "connect" in message_lower or "exchange" in message_lower:
            return "To connect an exchange, go to the Exchanges section and either use OAuth (for Coinbase) or enter your API keys. Make sure to create READ-ONLY keys for security."
        elif "chain of custody" in message_lower:
            return "Chain of Custody traces where your crypto came from by following transactions backwards. It helps establish accurate cost basis by finding the original acquisition point (exchange, DEX, etc.)."
        else:
            return "Thanks for your question! For detailed assistance, please email support@cryptobagtracker.io and we'll get back to you within 24-48 hours."
    
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
