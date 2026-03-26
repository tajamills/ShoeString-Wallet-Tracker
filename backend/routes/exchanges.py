"""Exchange routes - CSV import, API connections, transactions, Coinbase"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import Response
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import uuid
import io
import csv
import logging

from .dependencies import db, get_current_user, require_paid_tier
from .models import ExchangeConnectionRequest, CostBasisUpdate, ExchangeTaxRequest
from csv_parser_service import csv_parser_service
from exchange_tax_service import exchange_tax_service
from encryption_service import encryption_service
from multi_exchange_service import multi_exchange_service, MultiExchangeService, CoinbaseClient
from coinbase_oauth_service import coinbase_oauth_service, OAUTH_SCOPES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/exchanges", tags=["Exchanges"])


def _calculate_import_summary(transactions) -> Dict[str, Any]:
    """Calculate summary statistics from imported transactions"""
    summary = {
        "total_transactions": len(transactions),
        "by_type": {},
        "by_asset": {},
        "date_range": {"earliest": None, "latest": None}
    }
    
    for tx in transactions:
        tx_type = tx.tx_type
        summary["by_type"][tx_type] = summary["by_type"].get(tx_type, 0) + 1
        
        asset = tx.asset
        if asset not in summary["by_asset"]:
            summary["by_asset"][asset] = {"count": 0, "total_amount": 0}
        summary["by_asset"][asset]["count"] += 1
        summary["by_asset"][asset]["total_amount"] += tx.amount
        
        if tx.timestamp:
            ts = tx.timestamp.isoformat()
            if not summary["date_range"]["earliest"] or ts < summary["date_range"]["earliest"]:
                summary["date_range"]["earliest"] = ts
            if not summary["date_range"]["latest"] or ts > summary["date_range"]["latest"]:
                summary["date_range"]["latest"] = ts
    
    return summary


@router.get("/supported")
async def get_supported_exchanges():
    """Get list of supported exchange CSV formats with export instructions"""
    exchanges = csv_parser_service.get_supported_exchanges()
    return {"exchanges": exchanges}


@router.post("/import-csv")
async def import_exchange_csv(
    file: UploadFile = File(...),
    exchange_hint: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Import transactions from exchange CSV file"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="CSV import is an Unlimited feature. Upgrade to import exchange data."
            )
        
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Please upload a CSV file")
        
        content = await file.read()
        try:
            content_str = content.decode('utf-8')
        except UnicodeDecodeError:
            content_str = content.decode('latin-1')
        
        detected_exchange, transactions = csv_parser_service.parse_csv(
            content_str, 
            exchange_hint
        )
        
        stored_count = 0
        for tx in transactions:
            tx_doc = tx.to_dict()
            tx_doc["user_id"] = user["id"]
            tx_doc["imported_at"] = datetime.now(timezone.utc).isoformat()
            tx_doc["source"] = "csv_import"
            
            await db.exchange_transactions.update_one(
                {
                    "user_id": user["id"], 
                    "exchange": tx.exchange, 
                    "tx_id": tx.tx_id,
                    "timestamp": tx_doc["timestamp"]
                },
                {"$set": tx_doc},
                upsert=True
            )
            stored_count += 1
        
        logger.info(f"User {user['id']} imported {stored_count} transactions from {detected_exchange}")
        
        summary = _calculate_import_summary(transactions)
        
        return {
            "message": f"Successfully imported {stored_count} transactions from {detected_exchange.value}",
            "exchange_detected": detected_exchange.value,
            "transaction_count": stored_count,
            "summary": summary
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import CSV: {str(e)}")


@router.post("/convert-to-cointracker")
async def convert_ledger_to_cointracker(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """Convert Ledger Live CSV export to CoinTracker format
    
    CoinTracker format columns:
    Date, Received Quantity, Received Currency, Sent Quantity, Sent Currency, Fee Amount, Fee Currency, Tag
    """
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Please upload a CSV file")
        
        content = await file.read()
        try:
            content_str = content.decode('utf-8')
        except UnicodeDecodeError:
            content_str = content.decode('latin-1')
        
        # Parse the Ledger CSV
        detected_exchange, transactions = csv_parser_service.parse_csv(content_str)
        
        if not transactions:
            raise HTTPException(status_code=400, detail="No valid transactions found in the CSV")
        
        # Convert to CoinTracker format
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Date", "Received Quantity", "Received Currency", 
            "Sent Quantity", "Sent Currency", 
            "Fee Amount", "Fee Currency", "Tag"
        ])
        
        for tx in transactions:
            # Format date as MM/DD/YYYY HH:MM:SS (CoinTracker preferred format)
            date_str = tx.timestamp.strftime("%m/%d/%Y %H:%M:%S") if tx.timestamp else ""
            
            # Determine received vs sent based on transaction type
            received_qty = ""
            received_currency = ""
            sent_qty = ""
            sent_currency = ""
            fee_amount = ""
            fee_currency = ""
            # CoinTracker: Leave Tag EMPTY for trades/transfers - they auto-categorize
            # Only use tags for special cases: staking, stake, unstake, airdrop, gift, etc.
            tag = ""
            
            tx_type_lower = tx.tx_type.lower()
            
            if tx_type_lower in ["buy", "receive", "deposit", "in"]:
                # Receiving crypto
                received_qty = f"{tx.amount:.8f}".rstrip('0').rstrip('.')
                received_currency = tx.asset
                # If we have USD value, it was sent (fiat -> crypto)
                if tx.total_usd and tx.total_usd > 0:
                    sent_qty = f"{tx.total_usd:.2f}"
                    sent_currency = "USD"
                # Leave tag empty - CoinTracker auto-detects as Trade or Receive
                
            elif tx_type_lower in ["sell", "send", "withdrawal", "out"]:
                # Sending crypto
                sent_qty = f"{tx.amount:.8f}".rstrip('0').rstrip('.')
                sent_currency = tx.asset
                # If we have USD value, it was received (crypto -> fiat) - but only for sells
                if tx.total_usd and tx.total_usd > 0 and tx_type_lower == "sell":
                    received_qty = f"{tx.total_usd:.2f}"
                    received_currency = "USD"
                # Leave tag empty - CoinTracker auto-detects as Trade or Send
                
            elif tx_type_lower == "trade":
                # Crypto to crypto trade - need both sides
                sent_qty = f"{tx.amount:.8f}".rstrip('0').rstrip('.')
                sent_currency = tx.asset
                # Leave tag empty - CoinTracker auto-detects as Trade
            
            # Add fees if present
            if tx.fee and tx.fee > 0:
                fee_amount = f"{tx.fee:.8f}".rstrip('0').rstrip('.')
                fee_currency = tx.fee_asset or tx.asset
            
            # Write the row
            writer.writerow([
                date_str,
                received_qty,
                received_currency,
                sent_qty,
                sent_currency,
                fee_amount,
                fee_currency,
                tag
            ])
        
        # Get the CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Generate filename
        original_name = file.filename.replace('.csv', '')
        filename = f"{original_name}_cointracker_format.csv"
        
        logger.info(f"Converted {len(transactions)} transactions to CoinTracker format for user {user['id']}")
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error converting CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to convert CSV: {str(e)}")


@router.get("/transactions")
async def get_exchange_transactions(
    exchange: Optional[str] = None,
    tx_type: Optional[str] = None,
    asset: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user)
):
    """Get imported exchange transactions with filters"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Exchange transactions require Unlimited subscription."
            )
        
        query = {"user_id": user["id"]}
        
        if exchange:
            query["exchange"] = exchange.lower()
        if tx_type:
            query["tx_type"] = tx_type
        if asset:
            query["asset"] = asset.upper()
        
        transactions = await db.exchange_transactions.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        summary = {
            "total_transactions": len(transactions),
            "by_exchange": {},
            "by_type": {},
            "by_asset": {}
        }
        
        for tx in transactions:
            exc = tx.get("exchange", "unknown")
            summary["by_exchange"][exc] = summary["by_exchange"].get(exc, 0) + 1
            
            t = tx.get("tx_type", "unknown")
            summary["by_type"][t] = summary["by_type"].get(t, 0) + 1
            
            a = tx.get("asset", "unknown")
            summary["by_asset"][a] = summary["by_asset"].get(a, 0) + 1
        
        return {
            "transactions": transactions,
            "count": len(transactions),
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching exchange transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")


@router.delete("/transactions")
async def delete_exchange_transactions(
    exchange: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Delete imported exchange transactions"""
    try:
        query = {"user_id": user["id"]}
        if exchange:
            query["exchange"] = exchange.lower()
        
        result = await db.exchange_transactions.delete_many(query)
        
        return {
            "message": f"Deleted {result.deleted_count} transactions",
            "deleted_count": result.deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error deleting transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete transactions")


@router.put("/transactions/{tx_id}/cost-basis")
async def update_transaction_cost_basis(
    tx_id: str,
    update: CostBasisUpdate,
    user: dict = Depends(get_current_user)
):
    """Update cost basis and original purchase date for a transaction"""
    try:
        tx = await db.exchange_transactions.find_one({
            "user_id": user["id"],
            "tx_id": tx_id
        })
        
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        update_data = {}
        
        if update.is_transfer:
            update_data["is_transfer"] = True
            update_data["transfer_notes"] = update.notes or "Transfer from external wallet"
        
        if update.original_purchase_date:
            try:
                original_date = datetime.fromisoformat(update.original_purchase_date.replace("Z", "+00:00"))
                update_data["original_purchase_date"] = original_date
                update_data["acquisition_date_override"] = original_date
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DD)")
        
        if update.original_cost_basis is not None:
            update_data["original_cost_basis"] = update.original_cost_basis
            update_data["cost_basis_override"] = update.original_cost_basis
        
        if update.notes:
            update_data["user_notes"] = update.notes
        
        update_data["manually_adjusted"] = True
        update_data["adjusted_at"] = datetime.now(timezone.utc)
        
        await db.exchange_transactions.update_one(
            {"user_id": user["id"], "tx_id": tx_id},
            {"$set": update_data}
        )
        
        return {
            "message": "Transaction cost basis updated successfully",
            "tx_id": tx_id,
            "updates_applied": list(update_data.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating cost basis: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update transaction")


@router.get("/transactions/transfers")
async def get_potential_transfers(
    user: dict = Depends(get_current_user)
):
    """Identify potential transfers (receives that might be from external wallets)"""
    try:
        transactions = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("timestamp", 1).to_list(5000)
        
        potential_transfers = []
        receives_by_asset = {}
        
        for tx in transactions:
            if tx.get("tx_type") in ["receive", "deposit"]:
                asset = tx.get("asset", "")
                if asset not in receives_by_asset:
                    receives_by_asset[asset] = []
                receives_by_asset[asset].append(tx)
        
        for tx in transactions:
            if tx.get("tx_type") in ["sell", "send"]:
                asset = tx.get("asset", "")
                sell_time = tx.get("timestamp")
                
                if asset in receives_by_asset:
                    for receive in receives_by_asset[asset]:
                        receive_time = receive.get("timestamp")
                        if receive_time and sell_time:
                            if isinstance(receive_time, str):
                                receive_time = datetime.fromisoformat(receive_time.replace("Z", "+00:00"))
                            if isinstance(sell_time, str):
                                sell_time = datetime.fromisoformat(sell_time.replace("Z", "+00:00"))
                            
                            days_diff = (sell_time - receive_time).days
                            if 0 <= days_diff <= 30:
                                if not receive.get("is_transfer") and not receive.get("manually_adjusted"):
                                    potential_transfers.append({
                                        "receive_tx": receive,
                                        "sell_tx": tx,
                                        "days_between": days_diff,
                                        "asset": asset,
                                        "suggestion": f"This {asset} was received {days_diff} days before being sold. If transferred from your own wallet, set the original purchase date."
                                    })
        
        return {
            "potential_transfers": potential_transfers[:50],
            "count": len(potential_transfers),
            "message": "These receives may be transfers from your own wallets. Update the original purchase date if so."
        }
        
    except Exception as e:
        logger.error(f"Error finding potential transfers: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze transactions")


@router.get("/export-instructions/{exchange_id}")
async def get_export_instructions(exchange_id: str):
    """Get detailed CSV export instructions for a specific exchange"""
    instructions = {
        "coinbase": {
            "name": "Coinbase",
            "steps": [
                "1. Log in to Coinbase (coinbase.com)",
                "2. Click on your profile icon → Settings",
                "3. Go to 'Statements' or 'Reports'",
                "4. Click 'Generate Report'",
                "5. Select 'Transaction History'",
                "6. Choose your date range (or 'All time')",
                "7. Click 'Generate Report'",
                "8. Download the CSV file when ready"
            ],
            "notes": "We support multiple Coinbase CSV formats including classic and modern exports."
        },
        "binance": {
            "name": "Binance",
            "steps": [
                "1. Log in to Binance (binance.com)",
                "2. Go to 'Orders' → 'Trade History'",
                "3. Click 'Export' in the top right",
                "4. Select 'Export Complete Trade History'",
                "5. Choose your date range",
                "6. Click 'Generate' and wait for the file",
                "7. Download the CSV when ready"
            ],
            "notes": "For deposits/withdrawals, export separately from 'Wallet' → 'Transaction History'"
        },
        "kraken": {
            "name": "Kraken",
            "steps": [
                "1. Log in to Kraken (kraken.com)",
                "2. Go to 'History' in the top menu",
                "3. Click 'Export'",
                "4. Select 'Ledgers' for all transactions or 'Trades' for trades only",
                "5. Choose your date range",
                "6. Click 'Submit' and download the CSV"
            ],
            "notes": "Ledgers export includes all activity."
        },
        "gemini": {
            "name": "Gemini",
            "steps": [
                "1. Log in to Gemini (gemini.com)",
                "2. Go to 'Account' → 'Statements'",
                "3. Click 'Download' next to Trade History",
                "4. Select your date range",
                "5. Download the CSV file"
            ],
            "notes": "ActiveTrader interface has a separate export option."
        }
    }
    
    if exchange_id.lower() not in instructions:
        raise HTTPException(status_code=404, detail=f"Instructions not found for {exchange_id}")
    
    return instructions[exchange_id.lower()]


# Exchange Tax Calculation Routes
@router.post("/tax/calculate")
async def calculate_exchange_tax(
    request: ExchangeTaxRequest = ExchangeTaxRequest(),
    user: dict = Depends(get_current_user)
):
    """
    Calculate tax data from imported exchange CSVs only.
    
    Parameters:
        - asset_filter: Filter by specific asset (e.g., 'BTC')
        - tax_year: Filter by tax year (e.g., 2024)
        - as_of_date: Valuation date for unrealized gains (YYYY-MM-DD format)
                      If not provided and tax_year is set, defaults to Dec 31 of tax_year.
                      Use this for accurate end-of-year tax reporting.
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Exchange tax calculation requires Unlimited subscription."
            )
        
        transactions = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(10000)
        
        if not transactions:
            return {
                "message": "No exchange data found. Upload your exchange CSVs first.",
                "has_data": False,
                "tax_data": exchange_tax_service._empty_result()
            }
        
        tax_data = exchange_tax_service.calculate_from_transactions(
            transactions=transactions,
            asset_filter=request.asset_filter,
            tax_year=request.tax_year,
            as_of_date=request.as_of_date
        )
        
        return {
            "message": "Tax calculation complete",
            "has_data": True,
            "as_of_date": tax_data.get('as_of_date', 'current'),
            "valuation_note": tax_data.get('valuation_note', ''),
            "tax_data": tax_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating exchange tax: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate tax: {str(e)}")


@router.get("/tax/form-8949")
async def get_exchange_form_8949(
    tax_year: Optional[int] = None,
    holding_period: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Generate Form 8949 data from exchange transactions only"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Form 8949 export requires Unlimited subscription."
            )
        
        transactions = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(10000)
        
        if not transactions:
            return {
                "message": "No exchange data found",
                "line_items": [],
                "totals": {}
            }
        
        tax_data = exchange_tax_service.calculate_from_transactions(
            transactions=transactions,
            tax_year=tax_year
        )
        
        form_data = exchange_tax_service.generate_form_8949_data(
            realized_gains=tax_data['realized_gains'],
            holding_period_filter=holding_period
        )
        
        totals = {
            'total_proceeds': sum(item['proceeds'] for item in form_data),
            'total_cost_basis': sum(item['cost_basis'] for item in form_data),
            'total_gain_loss': sum(item['gain_or_loss'] for item in form_data),
            'line_count': len(form_data)
        }
        
        return {
            "tax_year": tax_year or "All Years",
            "holding_period": holding_period or "All",
            "line_items": form_data,
            "totals": totals
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating Form 8949: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate Form 8949")


@router.get("/tax/form-8949/csv")
async def export_exchange_form_8949_csv(
    tax_year: Optional[int] = None,
    holding_period: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export Form 8949 data as CSV file"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="CSV export requires Unlimited subscription."
            )
        
        transactions = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(10000)
        
        if not transactions:
            raise HTTPException(status_code=404, detail="No exchange data found")
        
        tax_data = exchange_tax_service.calculate_from_transactions(
            transactions=transactions,
            tax_year=tax_year
        )
        
        form_data = exchange_tax_service.generate_form_8949_data(
            realized_gains=tax_data['realized_gains'],
            holding_period_filter=holding_period
        )
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Description of Property',
            'Date Acquired',
            'Date Sold',
            'Proceeds',
            'Cost Basis',
            'Adjustment Code',
            'Adjustment Amount',
            'Gain or Loss',
            'Holding Period',
            'Exchange'
        ])
        
        for item in form_data:
            writer.writerow([
                item['description'],
                item['date_acquired'],
                item['date_sold'],
                f"${item['proceeds']:.2f}",
                f"${item['cost_basis']:.2f}",
                item['adjustment_code'],
                f"${item['adjustment_amount']:.2f}",
                f"${item['gain_or_loss']:.2f}",
                item['holding_period'],
                item['exchange']
            ])
        
        writer.writerow([])
        writer.writerow([
            'TOTALS', '', '',
            f"${sum(item['proceeds'] for item in form_data):.2f}",
            f"${sum(item['cost_basis'] for item in form_data):.2f}",
            '', '',
            f"${sum(item['gain_or_loss'] for item in form_data):.2f}",
            '', ''
        ])
        
        csv_content = output.getvalue()
        
        filename = f"Form_8949_Exchanges_{tax_year or 'All'}_{holding_period or 'All'}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export CSV")


# API Connection Routes
@router.post("/connect-api")
async def connect_exchange_api(
    request: ExchangeConnectionRequest,
    user: dict = Depends(get_current_user)
):
    """Connect an exchange using API keys"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="Exchange API integration requires a paid subscription."
            )
        
        exchange = request.exchange.lower()
        supported = ['binance', 'kraken', 'gemini', 'cryptocom', 'kucoin', 'okx', 'bybit', 'gateio', 'coinbase']
        
        if exchange not in supported:
            raise HTTPException(
                status_code=400,
                detail=f"Exchange not supported. Supported: {', '.join(supported)}"
            )
        
        encrypted_api_key = encryption_service.encrypt(request.api_key)
        encrypted_api_secret = encryption_service.encrypt(request.api_secret)
        encrypted_passphrase = encryption_service.encrypt(request.passphrase) if request.passphrase else None
        
        await db.exchange_connections.update_one(
            {"user_id": user["id"], "exchange": exchange},
            {
                "$set": {
                    "user_id": user["id"],
                    "exchange": exchange,
                    "api_key": encrypted_api_key,
                    "api_secret": encrypted_api_secret,
                    "passphrase": encrypted_passphrase,
                    "connected_at": datetime.now(timezone.utc),
                    "connection_type": "api_key",
                    "encrypted": True
                }
            },
            upsert=True
        )
        
        logger.info(f"{exchange.capitalize()} connected for user {user['id']}")
        
        return {
            "success": True,
            "message": f"{exchange.capitalize()} connected successfully",
            "exchange": exchange
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting exchange: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect exchange")


@router.get("/api-connections")
async def get_exchange_connections(user: dict = Depends(get_current_user)):
    """Get list of connected exchanges via API keys"""
    try:
        connections = await db.exchange_connections.find(
            {"user_id": user["id"]},
            {"_id": 0, "api_key": 0, "api_secret": 0}
        ).to_list(20)
        
        return {"connections": connections}
    
    except Exception as e:
        logger.error(f"Error fetching exchange connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch connections")


@router.delete("/disconnect-api/{exchange}")
async def disconnect_exchange_api(exchange: str, user: dict = Depends(get_current_user)):
    """Disconnect an exchange API connection"""
    try:
        result = await db.exchange_connections.delete_one({
            "user_id": user["id"],
            "exchange": exchange.lower()
        })
        
        if result.deleted_count > 0:
            return {"success": True, "message": f"{exchange.capitalize()} disconnected"}
        
        return {"success": False, "message": "Exchange not connected"}
    
    except Exception as e:
        logger.error(f"Error disconnecting exchange: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to disconnect exchange")


@router.get("/addresses-for-custody/{exchange}")
async def get_exchange_addresses_for_custody(
    exchange: str,
    user: dict = Depends(get_current_user)
):
    """Fetch addresses from a connected exchange for Chain of Custody analysis"""
    try:
        connection = await db.exchange_connections.find_one({
            "user_id": user["id"],
            "exchange": exchange.lower()
        })
        
        if not connection:
            raise HTTPException(
                status_code=400,
                detail=f"No {exchange} connection found. Please connect first."
            )
        
        api_key = connection['api_key']
        api_secret = connection['api_secret']
        passphrase = connection.get('passphrase')
        
        if connection.get('encrypted', False):
            api_key = encryption_service.decrypt(api_key)
            api_secret = encryption_service.decrypt(api_secret)
            if passphrase:
                passphrase = encryption_service.decrypt(passphrase)
        
        service = MultiExchangeService()
        service.add_exchange(
            exchange.lower(),
            api_key,
            api_secret,
            passphrase
        )
        
        logger.info(f"Fetching addresses from {exchange} for user {user['id']}")
        result = await service.get_addresses_for_custody(exchange.lower())
        
        wallet_count = len(result.get('wallet_addresses', []))
        logger.info(f"Found {wallet_count} wallet addresses from {exchange}")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching {exchange} addresses: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch {exchange} data: {str(e)}")


@router.get("/debug-coinbase")
async def debug_coinbase_connection(user: dict = Depends(get_current_user)):
    """Debug endpoint to test Coinbase connection"""
    try:
        connection = await db.exchange_connections.find_one({
            "user_id": user["id"],
            "exchange": "coinbase"
        })
        
        if not connection:
            return {"error": "No Coinbase connection found", "step": "connection_lookup"}
        
        api_key = connection['api_key']
        api_secret = connection['api_secret']
        
        if connection.get('encrypted', False):
            api_key = encryption_service.decrypt(api_key)
            api_secret = encryption_service.decrypt(api_secret)
        
        client = CoinbaseClient(api_key, api_secret)
        
        accounts = await client.get_accounts()
        account_summary = []
        for acc in accounts[:10]:
            account_summary.append({
                "id": acc.get('id', '')[:10] + "...",
                "name": acc.get('name', ''),
                "currency": acc.get('currency', {}).get('code', ''),
                "balance": acc.get('balance', {}).get('amount', '0')
            })
        
        addresses = await client.get_deposit_addresses()
        address_summary = []
        for addr in addresses[:10]:
            address_summary.append({
                "address": addr.address[:20] + "..." if len(addr.address) > 20 else addr.address,
                "asset": addr.asset,
                "network": addr.network
            })
        
        return {
            "status": "connected",
            "accounts_found": len(accounts),
            "accounts_sample": account_summary,
            "addresses_found": len(addresses),
            "addresses_sample": address_summary
        }
        
    except Exception as e:
        logger.error(f"Debug coinbase error: {e}", exc_info=True)
        return {"error": str(e), "step": "api_call"}


@router.post("/sync-coinbase")
async def sync_coinbase_transactions(user: dict = Depends(get_current_user)):
    """Sync all transactions from connected Coinbase account"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(status_code=403, detail="Exchange sync requires a paid subscription.")
        
        connection = await db.exchange_connections.find_one({
            "user_id": user["id"],
            "exchange": "coinbase"
        })
        
        if not connection:
            raise HTTPException(status_code=400, detail="No Coinbase connection found. Connect your API key first.")
        
        api_key = connection['api_key']
        api_secret = connection['api_secret']
        
        if connection.get('encrypted', False):
            api_key = encryption_service.decrypt(api_key)
            api_secret = encryption_service.decrypt(api_secret)
        
        client = CoinbaseClient(api_key, api_secret)
        transactions = await client.get_all_transactions()
        
        if not transactions:
            return {
                "message": "No transactions found in Coinbase",
                "synced_count": 0,
                "skipped_count": 0
            }
        
        synced = 0
        skipped = 0
        
        for tx in transactions:
            if tx.get('status') != 'completed' or tx.get('amount', 0) <= 0:
                skipped += 1
                continue
            
            tx['user_id'] = user['id']
            
            await db.exchange_transactions.update_one(
                {"user_id": user["id"], "tx_id": tx['tx_id']},
                {"$set": tx},
                upsert=True
            )
            synced += 1
        
        asset_counts = {}
        for tx in transactions:
            asset = tx.get('asset', 'UNKNOWN')
            asset_counts[asset] = asset_counts.get(asset, 0) + 1
        
        return {
            "message": f"Synced {synced} transactions from Coinbase",
            "synced_count": synced,
            "skipped_count": skipped,
            "assets": asset_counts,
            "total_fetched": len(transactions)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Coinbase sync error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
