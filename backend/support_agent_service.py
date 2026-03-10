"""
AI Support Agent Service
Provides help for cryptocurrency tax questions and app usage.
Currently using pre-written responses. Can be upgraded to AI later.
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SupportAgentService:
    """
    Support agent for answering user questions.
    Uses pre-written responses for common questions.
    """
    
    def __init__(self):
        self.conversations: Dict[str, List[Dict]] = {}
    
    async def get_response(
        self,
        user_id: str,
        message: str,
        conversation_history: List[Dict] = None
    ) -> Dict:
        """
        Get response to a user message using keyword matching.
        """
        try:
            session_id = f"support_{user_id}_{datetime.utcnow().strftime('%Y%m%d')}"
            response = self._get_fallback_response(message)
            
            return {
                "success": True,
                "response": response,
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"Support agent error: {str(e)}")
            return {
                "success": False,
                "response": "Something went wrong. Please email support@cryptobagtracker.io",
                "error": str(e)
            }
    
    def _get_fallback_response(self, message: str) -> str:
        """Provide helpful response based on keywords."""
        message_lower = message.lower()
        
        # Cost basis questions
        if "cost basis" in message_lower or "costbasis" in message_lower:
            return """**Cost Basis** is the original value of an asset for tax purposes.

**How we calculate it:**
- We use FIFO (First-In, First-Out) by default
- When you sell crypto, we match it against your oldest purchase first
- The difference between sale price and cost basis = your gain/loss

**Example:**
- You bought 1 BTC at $30,000
- You sold 1 BTC at $50,000
- Cost basis = $30,000
- Capital gain = $20,000

For personalized tax advice, please consult a tax professional."""

        # Capital gains questions
        elif "capital gain" in message_lower or "gains" in message_lower or "taxes" in message_lower:
            return """**Capital Gains** are profits from selling cryptocurrency.

**Two types:**
1. **Short-term** (held less than 1 year) - Taxed as ordinary income (10-37%)
2. **Long-term** (held more than 1 year) - Preferential rates (0%, 15%, or 20%)

**Taxable events:**
- Selling crypto for USD
- Trading one crypto for another
- Spending crypto on goods/services

**Non-taxable events:**
- Transferring between your own wallets
- Buying crypto with USD
- Holding crypto

For specific tax advice, consult a tax professional."""

        # Exchange connection questions
        elif "connect" in message_lower and "exchange" in message_lower:
            return """**Connecting Exchanges:**

**Option 1: Coinbase (OAuth)**
- Click "Chain of Custody" → "Connect Coinbase"
- Authorize read-only access
- We automatically import your addresses

**Option 2: Other Exchanges (API Keys)**
- Go to your exchange's API settings
- Create a NEW API key with READ-ONLY permissions
- Disable trading and withdrawals
- Enter the key in our app

**Supported Exchanges:**
Coinbase, Binance, Kraken, Gemini, Crypto.com, KuCoin, OKX, Bybit, Gate.io

**Security:** We only request read-only access. We cannot move your funds."""

        # Chain of custody questions
        elif "chain of custody" in message_lower or "custody" in message_lower:
            return """**Chain of Custody Analysis** traces where your crypto came from.

**How it works:**
1. Enter a wallet address
2. We trace transactions backwards
3. We identify origin points (exchanges, DEXs, dormant wallets)

**Why it matters:**
- Establishes accurate cost basis
- Proves source of funds for audits
- Helps with tax reporting

**Stop conditions:**
- Asset reached a known exchange (Binance, Coinbase, etc.)
- Asset came from a DEX swap
- Asset hasn't moved for 365+ days (dormant)

Available for Unlimited tier users."""

        # FIFO questions
        elif "fifo" in message_lower:
            return """**FIFO (First-In, First-Out)** is a cost basis method.

**How it works:**
- When you sell crypto, we match it against your OLDEST purchase first
- This affects your capital gains calculation

**Example:**
- Jan: Buy 1 BTC at $30,000
- Mar: Buy 1 BTC at $40,000
- Jun: Sell 1 BTC at $50,000

Using FIFO, the sale matches the January purchase:
- Cost basis = $30,000
- Capital gain = $20,000

Other methods (LIFO, HIFO) may result in different tax outcomes. Consult a tax professional for advice."""

        # Form 8949 questions
        elif "8949" in message_lower or "form" in message_lower or "schedule d" in message_lower:
            return """**IRS Form 8949** reports capital gains/losses from crypto.

**What we provide:**
- Automatic Form 8949 generation
- Separate short-term and long-term sections
- CSV export for TurboTax/TaxAct import

**How to use:**
1. Analyze your wallets
2. Import exchange transactions
3. Click "Export Form 8949"
4. Import into your tax software or give to your accountant

**Schedule D** summarizes your Form 8949 totals on your tax return."""

        # Transfer questions
        elif "transfer" in message_lower:
            return """**Wallet Transfers** are generally NOT taxable events.

**Why?**
- Moving crypto between your own wallets doesn't trigger a sale
- No gain or loss is realized
- Cost basis carries over to the new wallet

**Important:**
- Make sure both wallets are yours
- Keep records of transfers
- Our Chain of Custody feature can help track this

**What IS taxable:**
- Sending crypto as payment
- Transferring to someone else (may be a gift or sale)"""

        # Blockchain support questions
        elif "blockchain" in message_lower or "chain" in message_lower or "supported" in message_lower:
            return """**Supported Blockchains:**

✅ Ethereum (ETH)
✅ Bitcoin (BTC) - including xPub for HD wallets
✅ Polygon (MATIC)
✅ Arbitrum
✅ BSC (BNB Chain)
✅ Solana (SOL)
✅ Avalanche (AVAX)
✅ Optimism
✅ Base
✅ Dogecoin (DOGE)
✅ Algorand (ALGO)
✅ And more...

We're constantly adding new chains. Email us at support@cryptobagtracker.io to request a specific chain."""

        # Pricing/subscription questions
        elif "price" in message_lower or "subscription" in message_lower or "premium" in message_lower or "pro" in message_lower:
            return """**Subscription Tiers:**

**Free:**
- Ethereum analysis only
- Basic transaction history

**Premium:**
- Multi-chain support
- CSV export
- Advanced analytics

**Pro:**
- Everything in Premium
- "Analyze All Chains" feature
- Bitcoin xPub support

**Unlimited:**
- Everything in Pro
- Chain of Custody analysis
- PDF reports for auditors
- Priority support

Upgrade anytime from your dashboard!"""

        # Default response
        else:
            return """Thanks for reaching out! 

Here are some things I can help with:
• **Cost basis** - How we calculate your tax basis
• **Capital gains** - Short-term vs long-term taxes
• **Connecting exchanges** - Coinbase, Binance, Kraken, etc.
• **Chain of custody** - Tracing asset origins
• **Form 8949** - Tax report generation
• **FIFO** - Our cost basis method
• **Supported blockchains** - What we can analyze

For questions I can't answer, please email **support@cryptobagtracker.io** and we'll respond within 24-48 hours.

For tax advice specific to your situation, please consult a qualified tax professional."""
    
    def get_suggested_questions(self) -> List[str]:
        """Get list of suggested questions for users."""
        return [
            "How do I calculate my crypto capital gains?",
            "What's the difference between short-term and long-term gains?",
            "How do I connect my exchange?",
            "What is chain of custody analysis?",
            "Why is my cost basis showing as zero?",
            "How do wallet transfers affect my taxes?",
            "What is FIFO and how does it work?",
            "How do I generate Form 8949?",
            "What blockchains are supported?",
            "What subscription tier do I need?"
        ]


# Global service instance
support_agent_service = SupportAgentService()
