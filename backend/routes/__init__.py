# Route modules for Crypto Bag Tracker API
# Each module handles a specific domain of functionality

from .auth import router as auth_router
from .payments import router as payments_router
from .wallets import router as wallets_router
from .tax import router as tax_router
from .affiliates import router as affiliates_router
from .exchanges import router as exchanges_router
from .custody import router as custody_router
from .support import router as support_router

__all__ = [
    'auth_router',
    'payments_router', 
    'wallets_router',
    'tax_router',
    'affiliates_router',
    'exchanges_router',
    'custody_router',
    'support_router'
]
