"""
Classification Effectiveness Service

Measures whether the unknown transaction classifier materially improves 
tax readiness without introducing bad classifications.

Tracks:
- Before/after metrics for unknown counts, validation status, export readiness
- Precision metrics by confidence bucket
- Metrics by classification type
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceBucketMetrics:
    """Metrics for a specific confidence bucket"""
    bucket_name: str
    min_confidence: float
    max_confidence: float
    total_classified: int = 0
    user_confirmed: int = 0
    user_rejected: int = 0
    rollback_count: int = 0
    precision: float = 0.0  # user_confirmed / (user_confirmed + user_rejected)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ClassificationTypeMetrics:
    """Metrics for a specific classification type"""
    classification_type: str
    total_classified: int = 0
    auto_classified: int = 0
    user_confirmed: int = 0
    user_rejected: int = 0
    rollback_count: int = 0
    precision: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AccountEffectivenessSnapshot:
    """Snapshot of account state before/after classification"""
    snapshot_id: str
    user_id: str
    timestamp: str
    snapshot_type: str  # 'before' or 'after'
    unknown_count: int
    validation_status: str
    can_export: bool
    blocking_issues_count: int
    unresolved_review_count: int
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class EffectivenessSummary:
    """Overall effectiveness summary for an account"""
    user_id: str
    period_start: str
    period_end: str
    
    # Before/After comparisons
    unknown_count_before: int = 0
    unknown_count_after: int = 0
    unknown_reduction: int = 0
    unknown_reduction_pct: float = 0.0
    
    auto_classified_count: int = 0
    user_confirmed_count: int = 0
    user_rejected_count: int = 0
    rollback_count: int = 0
    
    validation_status_before: str = "unknown"
    validation_status_after: str = "unknown"
    can_export_before: bool = False
    can_export_after: bool = False
    
    # Export readiness improvement
    export_readiness_improved: bool = False
    
    # Confidence bucket metrics
    confidence_buckets: List[Dict] = None
    
    # Classification type metrics
    classification_types: List[Dict] = None
    
    # Overall precision
    overall_precision: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "unknown_count_before": self.unknown_count_before,
            "unknown_count_after": self.unknown_count_after,
            "unknown_reduction": self.unknown_reduction,
            "unknown_reduction_pct": round(self.unknown_reduction_pct, 2),
            "auto_classified_count": self.auto_classified_count,
            "user_confirmed_count": self.user_confirmed_count,
            "user_rejected_count": self.user_rejected_count,
            "rollback_count": self.rollback_count,
            "validation_status_before": self.validation_status_before,
            "validation_status_after": self.validation_status_after,
            "can_export_before": self.can_export_before,
            "can_export_after": self.can_export_after,
            "export_readiness_improved": self.export_readiness_improved,
            "confidence_buckets": self.confidence_buckets or [],
            "classification_types": self.classification_types or [],
            "overall_precision": round(self.overall_precision, 3)
        }


class ClassificationEffectivenessService:
    """
    Service for tracking and measuring classification effectiveness.
    """
    
    # Confidence buckets
    CONFIDENCE_BUCKETS = [
        {"name": "high", "min": 0.95, "max": 1.0},
        {"name": "medium_high", "min": 0.85, "max": 0.95},
        {"name": "medium", "min": 0.70, "max": 0.85},
        {"name": "low", "min": 0.0, "max": 0.70}
    ]
    
    # Classification types to track
    CLASSIFICATION_TYPES = [
        "internal_transfer",
        "external_transfer",
        "swap",
        "bridge",
        "deposit",
        "withdrawal",
        "buy",
        "sell",
        "reward",
        "staking"
    ]
    
    def __init__(self, db):
        self.db = db
    
    async def capture_snapshot(
        self,
        user_id: str,
        snapshot_type: str  # 'before' or 'after'
    ) -> AccountEffectivenessSnapshot:
        """
        Capture current account state for before/after comparison.
        """
        # Get current unknown count
        unknown_count = await self.db.exchange_transactions.count_documents({
            "user_id": user_id,
            "tx_type": "unknown"
        })
        
        # Get validation status
        validation_status = "unknown"
        can_export = False
        blocking_issues = 0
        unresolved_reviews = 0
        
        try:
            # Check pre-export status
            from beta_validation_harness import BetaValidationHarness
            harness = BetaValidationHarness(self.db)
            pre_export = await harness.pre_export_check(user_id)
            
            validation_status = pre_export.get("validation_status", "unknown")
            can_export = pre_export.get("can_export", False)
            blocking_issues = pre_export.get("blocking_issues_count", 0)
            unresolved_reviews = pre_export.get("unresolved_review_count", 0)
        except Exception as e:
            logger.warning(f"Could not get validation status: {e}")
        
        snapshot = AccountEffectivenessSnapshot(
            snapshot_id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            snapshot_type=snapshot_type,
            unknown_count=unknown_count,
            validation_status=validation_status,
            can_export=can_export,
            blocking_issues_count=blocking_issues,
            unresolved_review_count=unresolved_reviews
        )
        
        # Store snapshot
        await self.db.classification_effectiveness_snapshots.insert_one(snapshot.to_dict())
        
        return snapshot
    
    async def record_classification_event(
        self,
        user_id: str,
        tx_id: str,
        classification_type: str,
        confidence: float,
        auto_applied: bool,
        batch_id: Optional[str] = None
    ):
        """
        Record a classification event for effectiveness tracking.
        """
        event = {
            "event_id": str(uuid.uuid4()),
            "user_id": user_id,
            "tx_id": tx_id,
            "classification_type": classification_type,
            "confidence": confidence,
            "confidence_bucket": self._get_confidence_bucket(confidence),
            "auto_applied": auto_applied,
            "batch_id": batch_id,
            "user_feedback": None,  # Will be updated when user confirms/rejects
            "rolled_back": False,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await self.db.classification_effectiveness_events.insert_one(event)
        return event
    
    async def record_user_feedback(
        self,
        user_id: str,
        tx_id: str,
        accepted: bool
    ):
        """
        Record user feedback (confirm/reject) for a classification.
        """
        await self.db.classification_effectiveness_events.update_one(
            {"user_id": user_id, "tx_id": tx_id, "user_feedback": None},
            {
                "$set": {
                    "user_feedback": "accepted" if accepted else "rejected",
                    "feedback_timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        )
    
    async def record_rollback(
        self,
        user_id: str,
        batch_id: str
    ):
        """
        Record a rollback event.
        """
        await self.db.classification_effectiveness_events.update_many(
            {"user_id": user_id, "batch_id": batch_id},
            {
                "$set": {
                    "rolled_back": True,
                    "rollback_timestamp": datetime.now(timezone.utc).isoformat()
                }
            }
        )
    
    async def get_effectiveness_summary(
        self,
        user_id: str,
        days: int = 30
    ) -> EffectivenessSummary:
        """
        Get comprehensive effectiveness summary for an account.
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)
        period_end = datetime.now(timezone.utc)
        
        # Get all classification events in period
        events = await self.db.classification_effectiveness_events.find({
            "user_id": user_id,
            "timestamp": {"$gte": period_start.isoformat()}
        }).to_list(100000)
        
        # Get snapshots
        snapshots = await self.db.classification_effectiveness_snapshots.find({
            "user_id": user_id,
            "timestamp": {"$gte": period_start.isoformat()}
        }).sort("timestamp", 1).to_list(1000)
        
        # Calculate before/after from snapshots
        before_snapshot = next((s for s in snapshots if s["snapshot_type"] == "before"), None)
        after_snapshots = [s for s in snapshots if s["snapshot_type"] == "after"]
        after_snapshot = after_snapshots[-1] if after_snapshots else None
        
        # If no snapshots, get current state
        if not before_snapshot:
            unknown_before = await self._get_historical_unknown_count(user_id, period_start)
            validation_before = "unknown"
            can_export_before = False
        else:
            unknown_before = before_snapshot["unknown_count"]
            validation_before = before_snapshot["validation_status"]
            can_export_before = before_snapshot["can_export"]
        
        if not after_snapshot:
            unknown_after = await self.db.exchange_transactions.count_documents({
                "user_id": user_id,
                "tx_type": "unknown"
            })
            # Get current validation status
            try:
                from beta_validation_harness import BetaValidationHarness
                harness = BetaValidationHarness(self.db)
                pre_export = await harness.pre_export_check(user_id)
                validation_after = pre_export.get("validation_status", "unknown")
                can_export_after = pre_export.get("can_export", False)
            except Exception:
                validation_after = "unknown"
                can_export_after = False
        else:
            unknown_after = after_snapshot["unknown_count"]
            validation_after = after_snapshot["validation_status"]
            can_export_after = after_snapshot["can_export"]
        
        # Calculate basic metrics
        auto_classified = sum(1 for e in events if e.get("auto_applied") and not e.get("rolled_back"))
        user_confirmed = sum(1 for e in events if e.get("user_feedback") == "accepted")
        user_rejected = sum(1 for e in events if e.get("user_feedback") == "rejected")
        rollback_count = sum(1 for e in events if e.get("rolled_back"))
        
        unknown_reduction = unknown_before - unknown_after
        unknown_reduction_pct = (unknown_reduction / unknown_before * 100) if unknown_before > 0 else 0
        
        # Calculate confidence bucket metrics
        confidence_buckets = await self._calculate_confidence_bucket_metrics(events)
        
        # Calculate classification type metrics
        classification_types = await self._calculate_classification_type_metrics(events)
        
        # Calculate overall precision
        total_feedback = user_confirmed + user_rejected
        overall_precision = user_confirmed / total_feedback if total_feedback > 0 else 0.0
        
        # Determine if export readiness improved
        export_improved = (not can_export_before and can_export_after) or \
                         (validation_before in ["invalid", "needs_review"] and validation_after == "valid")
        
        summary = EffectivenessSummary(
            user_id=user_id,
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            unknown_count_before=unknown_before,
            unknown_count_after=unknown_after,
            unknown_reduction=unknown_reduction,
            unknown_reduction_pct=unknown_reduction_pct,
            auto_classified_count=auto_classified,
            user_confirmed_count=user_confirmed,
            user_rejected_count=user_rejected,
            rollback_count=rollback_count,
            validation_status_before=validation_before,
            validation_status_after=validation_after,
            can_export_before=can_export_before,
            can_export_after=can_export_after,
            export_readiness_improved=export_improved,
            confidence_buckets=confidence_buckets,
            classification_types=classification_types,
            overall_precision=overall_precision
        )
        
        return summary
    
    async def get_precision_by_confidence_bucket(
        self,
        user_id: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get precision metrics broken down by confidence bucket.
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)
        
        events = await self.db.classification_effectiveness_events.find({
            "user_id": user_id,
            "timestamp": {"$gte": period_start.isoformat()},
            "user_feedback": {"$ne": None}
        }).to_list(100000)
        
        return await self._calculate_confidence_bucket_metrics(events)
    
    async def get_precision_by_classification_type(
        self,
        user_id: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get precision metrics broken down by classification type.
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)
        
        events = await self.db.classification_effectiveness_events.find({
            "user_id": user_id,
            "timestamp": {"$gte": period_start.isoformat()}
        }).to_list(100000)
        
        return await self._calculate_classification_type_metrics(events)
    
    async def get_all_accounts_summary(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get aggregated effectiveness summary across all accounts.
        """
        period_start = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get all users with classification events
        pipeline = [
            {"$match": {"timestamp": {"$gte": period_start.isoformat()}}},
            {"$group": {"_id": "$user_id"}}
        ]
        user_ids = [doc["_id"] for doc in await self.db.classification_effectiveness_events.aggregate(pipeline).to_list(1000)]
        
        if not user_ids:
            return {
                "period_days": days,
                "accounts_count": 0,
                "total_auto_classified": 0,
                "total_user_confirmed": 0,
                "total_user_rejected": 0,
                "total_rollbacks": 0,
                "aggregate_precision": 0.0,
                "accounts_improved": 0,
                "confidence_buckets": [],
                "classification_types": []
            }
        
        # Aggregate events
        all_events = await self.db.classification_effectiveness_events.find({
            "timestamp": {"$gte": period_start.isoformat()}
        }).to_list(1000000)
        
        auto_classified = sum(1 for e in all_events if e.get("auto_applied") and not e.get("rolled_back"))
        user_confirmed = sum(1 for e in all_events if e.get("user_feedback") == "accepted")
        user_rejected = sum(1 for e in all_events if e.get("user_feedback") == "rejected")
        rollback_count = sum(1 for e in all_events if e.get("rolled_back"))
        
        total_feedback = user_confirmed + user_rejected
        aggregate_precision = user_confirmed / total_feedback if total_feedback > 0 else 0.0
        
        # Count accounts with improved export readiness
        accounts_improved = 0
        for uid in user_ids:
            summary = await self.get_effectiveness_summary(uid, days)
            if summary.export_readiness_improved:
                accounts_improved += 1
        
        # Aggregate confidence buckets
        confidence_buckets = await self._calculate_confidence_bucket_metrics(all_events)
        
        # Aggregate classification types
        classification_types = await self._calculate_classification_type_metrics(all_events)
        
        return {
            "period_days": days,
            "accounts_count": len(user_ids),
            "total_auto_classified": auto_classified,
            "total_user_confirmed": user_confirmed,
            "total_user_rejected": user_rejected,
            "total_rollbacks": rollback_count,
            "aggregate_precision": round(aggregate_precision, 3),
            "accounts_improved": accounts_improved,
            "confidence_buckets": confidence_buckets,
            "classification_types": classification_types
        }
    
    # === PRIVATE METHODS ===
    
    def _get_confidence_bucket(self, confidence: float) -> str:
        """Get the bucket name for a confidence value."""
        for bucket in self.CONFIDENCE_BUCKETS:
            if bucket["min"] <= confidence <= bucket["max"]:
                return bucket["name"]
        return "low"
    
    async def _calculate_confidence_bucket_metrics(
        self,
        events: List[Dict]
    ) -> List[Dict]:
        """Calculate metrics per confidence bucket."""
        buckets = {}
        
        for bucket in self.CONFIDENCE_BUCKETS:
            buckets[bucket["name"]] = ConfidenceBucketMetrics(
                bucket_name=bucket["name"],
                min_confidence=bucket["min"],
                max_confidence=bucket["max"]
            )
        
        for event in events:
            bucket_name = event.get("confidence_bucket", "low")
            if bucket_name not in buckets:
                bucket_name = "low"
            
            bucket = buckets[bucket_name]
            bucket.total_classified += 1
            
            if event.get("user_feedback") == "accepted":
                bucket.user_confirmed += 1
            elif event.get("user_feedback") == "rejected":
                bucket.user_rejected += 1
            
            if event.get("rolled_back"):
                bucket.rollback_count += 1
        
        # Calculate precision for each bucket
        for bucket in buckets.values():
            total = bucket.user_confirmed + bucket.user_rejected
            bucket.precision = bucket.user_confirmed / total if total > 0 else 0.0
        
        return [b.to_dict() for b in buckets.values()]
    
    async def _calculate_classification_type_metrics(
        self,
        events: List[Dict]
    ) -> List[Dict]:
        """Calculate metrics per classification type."""
        types = {}
        
        for ct in self.CLASSIFICATION_TYPES:
            types[ct] = ClassificationTypeMetrics(classification_type=ct)
        
        for event in events:
            ct = event.get("classification_type", "unknown")
            if ct not in types:
                types[ct] = ClassificationTypeMetrics(classification_type=ct)
            
            metrics = types[ct]
            metrics.total_classified += 1
            
            if event.get("auto_applied"):
                metrics.auto_classified += 1
            
            if event.get("user_feedback") == "accepted":
                metrics.user_confirmed += 1
            elif event.get("user_feedback") == "rejected":
                metrics.user_rejected += 1
            
            if event.get("rolled_back"):
                metrics.rollback_count += 1
        
        # Calculate precision for each type
        for metrics in types.values():
            total = metrics.user_confirmed + metrics.user_rejected
            metrics.precision = metrics.user_confirmed / total if total > 0 else 0.0
        
        # Filter out types with no classifications
        return [m.to_dict() for m in types.values() if m.total_classified > 0]
    
    async def _get_historical_unknown_count(
        self,
        user_id: str,
        as_of: datetime
    ) -> int:
        """
        Estimate unknown count at a historical point.
        This is an approximation based on audit trail.
        """
        # Count current unknowns
        current = await self.db.exchange_transactions.count_documents({
            "user_id": user_id,
            "tx_type": "unknown"
        })
        
        # Add back classifications made after as_of
        classified_after = await self.db.classification_audit.count_documents({
            "user_id": user_id,
            "timestamp": {"$gte": as_of.isoformat()},
            "original_type": "unknown"
        })
        
        return current + classified_after
