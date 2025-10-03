from sqlalchemy.orm import Session
from models import Transaction, RecurringSubscription
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import re
from collections import defaultdict
import statistics


class RecurrenceDetector:
    def __init__(self, db: Session):
        self.db = db

    def normalize_merchant_name(self, merchant: str) -> str:
        """Normalize merchant names for better grouping"""
        # Convert to lowercase and remove common variations
        normalized = merchant.lower().strip()
        
        # Remove common suffixes
        suffixes_to_remove = [
            r'\s+inc\.?$', r'\s+llc\.?$', r'\s+ltd\.?$', r'\s+corp\.?$',
            r'\s+company$', r'\s+co\.?$', r'\s+limited$'
        ]
        
        for suffix in suffixes_to_remove:
            normalized = re.sub(suffix, '', normalized)
        
        # Remove common prefixes
        prefixes_to_remove = [
            r'^the\s+', r'^a\s+', r'^an\s+'
        ]
        
        for prefix in prefixes_to_remove:
            normalized = re.sub(prefix, '', normalized)
        
        return normalized.strip()

    def detect_recurring_subscriptions(self) -> List[RecurringSubscription]:
        """Detect recurring subscriptions from transaction history"""
        # Get all transactions
        transactions = self.db.query(Transaction).order_by(Transaction.date).all()
        
        # Group transactions by normalized merchant name
        merchant_groups = defaultdict(list)
        for transaction in transactions:
            normalized_merchant = self.normalize_merchant_name(transaction.merchant)
            merchant_groups[normalized_merchant].append(transaction)
        
        detected_subscriptions = []
        
        for normalized_merchant, merchant_transactions in merchant_groups.items():
            if len(merchant_transactions) < 2:
                continue
                
            # Sort by date
            merchant_transactions.sort(key=lambda x: x.date)
            
            # Calculate intervals between transactions
            intervals = []
            for i in range(1, len(merchant_transactions)):
                interval = (merchant_transactions[i].date - merchant_transactions[i-1].date).days
                intervals.append(interval)
            
            if not intervals:
                continue
            
            # Check if intervals are consistent (within 30±7 days for monthly)
            median_interval = statistics.median(intervals)
            if 23 <= median_interval <= 37:  # Monthly subscription range
                # Calculate confidence score based on consistency
                consistent_intervals = [i for i in intervals if 23 <= i <= 37]
                confidence = len(consistent_intervals) / len(intervals)
                
                if confidence >= 0.5:  # At least 50% of intervals are monthly
                    # Get the most recent transaction
                    last_transaction = merchant_transactions[-1]
                    
                    # Calculate next due date
                    next_due_date = last_transaction.date + timedelta(days=median_interval)
                    
                    # Create source transparency info
                    source_info = self._create_source_transparency(merchant_transactions)
                    
                    # Check if subscription already exists
                    existing = self.db.query(RecurringSubscription).filter(
                        RecurringSubscription.merchant == last_transaction.merchant
                    ).first()
                    
                    if existing:
                        # Update existing subscription
                        existing.amount = last_transaction.amount
                        existing.interval_days = int(median_interval)
                        existing.last_paid_date = last_transaction.date
                        existing.next_due_date = next_due_date
                        existing.confidence_score = confidence
                        existing.source_transparency = source_info
                        existing.updated_at = datetime.utcnow()
                    else:
                        # Create new subscription
                        subscription = RecurringSubscription(
                            merchant=last_transaction.merchant,
                            amount=last_transaction.amount,
                            interval_days=int(median_interval),
                            last_paid_date=last_transaction.date,
                            next_due_date=next_due_date,
                            confidence_score=confidence,
                            source_transparency=source_info
                        )
                        self.db.add(subscription)
                        detected_subscriptions.append(subscription)
        
        self.db.commit()
        return detected_subscriptions

    def _create_source_transparency(self, transactions: List[Transaction]) -> str:
        """Create human-readable source transparency information"""
        sources = []
        for transaction in transactions:
            if transaction.source == "gmail":
                sources.append(f"Gmail receipt on {transaction.date.strftime('%Y-%m-%d')}")
            elif transaction.source == "upload":
                sources.append(f"Uploaded file on {transaction.date.strftime('%Y-%m-%d')}")
            elif transaction.source == "mock":
                sources.append(f"Mock data on {transaction.date.strftime('%Y-%m-%d')}")
        
        # Remove duplicates and limit to recent sources
        unique_sources = list(dict.fromkeys(sources))[-3:]  # Last 3 unique sources
        return "; ".join(unique_sources)

