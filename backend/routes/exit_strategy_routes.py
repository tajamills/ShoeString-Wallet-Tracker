"""
Exit Strategy Models and Routes
Allows users to create multi-asset exit strategies with alert integration
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import os

from motor.motor_asyncio import AsyncIOMotorClient
from routes.dependencies import get_current_user

router = APIRouter()

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'test_database')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]


# ========== MODELS ==========

class ExitTier(BaseModel):
    tier_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    sell_percentage: float  # 0-100
    target_price: float
    alert_created: bool = False
    alert_id: Optional[str] = None
    executed: bool = False
    executed_at: Optional[datetime] = None


class ExitStrategy(BaseModel):
    strategy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    asset_symbol: str  # e.g., "BTC", "ETH"
    quantity: float
    average_cost_basis: float
    tax_rate: float  # Capital gains rate 0-100
    tiers: List[ExitTier] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateExitStrategyRequest(BaseModel):
    asset_symbol: str
    quantity: float
    average_cost_basis: float
    tax_rate: float = 15.0
    tiers: List[dict] = []


class UpdateExitStrategyRequest(BaseModel):
    quantity: Optional[float] = None
    average_cost_basis: Optional[float] = None
    tax_rate: Optional[float] = None
    tiers: Optional[List[dict]] = None


class CreateAlertsFromStrategyRequest(BaseModel):
    strategy_id: str
    notification_method: str = "email"  # email, sms, telegram


# ========== ROUTES ==========

@router.get("/strategies")
async def get_exit_strategies(user: dict = Depends(get_current_user)):
    """Get all exit strategies for user"""
    strategies = await db.exit_strategies.find(
        {"user_id": user["id"]},
        {"_id": 0}
    ).to_list(length=100)
    
    return {
        "strategies": strategies,
        "count": len(strategies)
    }


@router.get("/strategies/{strategy_id}")
async def get_exit_strategy(strategy_id: str, user: dict = Depends(get_current_user)):
    """Get a specific exit strategy"""
    strategy = await db.exit_strategies.find_one(
        {"user_id": user["id"], "strategy_id": strategy_id},
        {"_id": 0}
    )
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return strategy


@router.post("/strategies")
async def create_exit_strategy(
    request: CreateExitStrategyRequest,
    user: dict = Depends(get_current_user)
):
    """Create a new exit strategy for an asset"""
    
    # Check if strategy already exists for this asset
    existing = await db.exit_strategies.find_one({
        "user_id": user["id"],
        "asset_symbol": request.asset_symbol.upper()
    })
    
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Exit strategy for {request.asset_symbol} already exists. Update it instead."
        )
    
    # Create tiers with IDs
    tiers = []
    for i, tier_data in enumerate(request.tiers):
        tiers.append(ExitTier(
            name=tier_data.get("name", f"Tier {i+1}"),
            sell_percentage=tier_data.get("sell_percentage", tier_data.get("sellPercentage", 25)),
            target_price=tier_data.get("target_price", tier_data.get("targetPrice", 50000))
        ).model_dump())
    
    strategy = ExitStrategy(
        user_id=user["id"],
        asset_symbol=request.asset_symbol.upper(),
        quantity=request.quantity,
        average_cost_basis=request.average_cost_basis,
        tax_rate=request.tax_rate,
        tiers=tiers
    )
    
    await db.exit_strategies.insert_one(strategy.model_dump())
    
    return {
        "success": True,
        "strategy_id": strategy.strategy_id,
        "message": f"Exit strategy created for {request.asset_symbol}"
    }


@router.put("/strategies/{strategy_id}")
async def update_exit_strategy(
    strategy_id: str,
    request: UpdateExitStrategyRequest,
    user: dict = Depends(get_current_user)
):
    """Update an exit strategy"""
    
    update_data = {"updated_at": datetime.now(timezone.utc)}
    
    if request.quantity is not None:
        update_data["quantity"] = request.quantity
    if request.average_cost_basis is not None:
        update_data["average_cost_basis"] = request.average_cost_basis
    if request.tax_rate is not None:
        update_data["tax_rate"] = request.tax_rate
    if request.tiers is not None:
        # Process tiers
        tiers = []
        for i, tier_data in enumerate(request.tiers):
            tiers.append({
                "tier_id": tier_data.get("tier_id", str(uuid.uuid4())),
                "name": tier_data.get("name", f"Tier {i+1}"),
                "sell_percentage": tier_data.get("sell_percentage", tier_data.get("sellPercentage", 25)),
                "target_price": tier_data.get("target_price", tier_data.get("targetPrice", 50000)),
                "alert_created": tier_data.get("alert_created", False),
                "alert_id": tier_data.get("alert_id"),
                "executed": tier_data.get("executed", False),
                "executed_at": tier_data.get("executed_at")
            })
        update_data["tiers"] = tiers
    
    result = await db.exit_strategies.update_one(
        {"user_id": user["id"], "strategy_id": strategy_id},
        {"$set": update_data}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return {"success": True, "message": "Strategy updated"}


@router.delete("/strategies/{strategy_id}")
async def delete_exit_strategy(strategy_id: str, user: dict = Depends(get_current_user)):
    """Delete an exit strategy"""
    
    result = await db.exit_strategies.delete_one({
        "user_id": user["id"],
        "strategy_id": strategy_id
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return {"success": True, "message": "Strategy deleted"}


@router.post("/strategies/{strategy_id}/create-alerts")
async def create_alerts_from_strategy(
    strategy_id: str,
    request: CreateAlertsFromStrategyRequest,
    user: dict = Depends(get_current_user)
):
    """Create price alerts from exit strategy tiers"""
    
    # Get strategy
    strategy = await db.exit_strategies.find_one({
        "user_id": user["id"],
        "strategy_id": strategy_id
    })
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    alerts_created = 0
    updated_tiers = []
    
    for tier in strategy.get("tiers", []):
        # Skip if alert already created or tier executed
        if tier.get("alert_created") or tier.get("executed"):
            updated_tiers.append(tier)
            continue
        
        # Create alert for this tier
        alert_id = str(uuid.uuid4())
        
        alert_data = {
            "alert_id": alert_id,
            "user_id": user["id"],
            "asset_symbol": strategy["asset_symbol"],
            "asset_type": "crypto",
            "alert_type": "price_above",  # Exit = sell when price above target
            "target_value": tier["target_price"],
            "notification_method": request.notification_method,
            "status": "active",
            "note": f"EXIT STRATEGY: {tier['name']} - Sell {tier['sell_percentage']}% of {strategy['asset_symbol']} at ${tier['target_price']:,.2f}",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_exit_strategy": True,
            "exit_strategy_id": strategy_id,
            "exit_tier_id": tier["tier_id"]
        }
        
        await db.alerts.insert_one(alert_data)
        alerts_created += 1
        
        # Update tier with alert info
        tier["alert_created"] = True
        tier["alert_id"] = alert_id
        updated_tiers.append(tier)
    
    # Update strategy with new tier data
    await db.exit_strategies.update_one(
        {"strategy_id": strategy_id},
        {"$set": {"tiers": updated_tiers, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {
        "success": True,
        "alerts_created": alerts_created,
        "message": f"Created {alerts_created} alert(s) for {strategy['asset_symbol']} exit strategy"
    }


@router.post("/strategies/{strategy_id}/tiers/{tier_id}/mark-executed")
async def mark_tier_executed(
    strategy_id: str,
    tier_id: str,
    user: dict = Depends(get_current_user)
):
    """Mark a tier as executed (user sold at that price)"""
    
    strategy = await db.exit_strategies.find_one({
        "user_id": user["id"],
        "strategy_id": strategy_id
    })
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    updated_tiers = []
    tier_found = False
    
    for tier in strategy.get("tiers", []):
        if tier["tier_id"] == tier_id:
            tier["executed"] = True
            tier["executed_at"] = datetime.now(timezone.utc).isoformat()
            tier_found = True
            
            # Deactivate the associated alert if exists
            if tier.get("alert_id"):
                await db.alerts.update_one(
                    {"alert_id": tier["alert_id"]},
                    {"$set": {"status": "triggered"}}
                )
        updated_tiers.append(tier)
    
    if not tier_found:
        raise HTTPException(status_code=404, detail="Tier not found")
    
    await db.exit_strategies.update_one(
        {"strategy_id": strategy_id},
        {"$set": {"tiers": updated_tiers, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "message": "Tier marked as executed"}
