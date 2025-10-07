"""
Enhanced Recurrence Detection Module for LifeAdmin MVP
Handles recurring charge/task detection with confidence scoring
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from collections import defaultdict, Counter

from models import Task, Transaction


class EnhancedRecurrenceDetector:
    """Enhanced recurrence detection for tasks and transactions"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def detect_recurring_tasks(self) -> List[Dict[str, Any]]:
        """Detect recurring tasks from Gmail and other sources"""
        # Get all tasks from Gmail source
        gmail_tasks = self.db.query(Task).filter(
            Task.source == 'gmail',
            Task.is_active == True
        ).all()
        
        # Group tasks by name
        task_groups = defaultdict(list)
        for task in gmail_tasks:
            task_groups[task.name].append(task)
        
        recurring_tasks = []
        
        for task_name, tasks in task_groups.items():
            if len(tasks) >= 2:  # Need at least 2 instances to detect recurrence
                recurrence_info = self._analyze_task_recurrence(tasks)
                
                if recurrence_info['confidence_score'] > 0.3:  # Minimum confidence threshold
                    recurring_tasks.append({
                        'name': task_name,
                        'tasks': tasks,
                        'recurrence_info': recurrence_info
                    })
        
        return recurring_tasks
    
    def _analyze_task_recurrence(self, tasks: List[Task]) -> Dict[str, Any]:
        """Analyze recurrence pattern for a group of tasks"""
        if len(tasks) < 2:
            return {'confidence_score': 0.0, 'interval_days': None}
        
        # Sort tasks by creation date
        sorted_tasks = sorted(tasks, key=lambda t: t.created_at)
        
        # Calculate intervals between tasks
        intervals = []
        for i in range(1, len(sorted_tasks)):
            interval = (sorted_tasks[i].created_at - sorted_tasks[i-1].created_at).days
            intervals.append(interval)
        
        if not intervals:
            return {'confidence_score': 0.0, 'interval_days': None}
        
        # Calculate statistics
        median_interval = np.median(intervals)
        std_interval = np.std(intervals)
        mean_interval = np.mean(intervals)
        
        # Calculate confidence score based on consistency
        consistency_score = self._calculate_consistency_score(intervals)
        
        # Factor in number of occurrences
        occurrence_score = min(len(tasks) / 5.0, 1.0)  # Max score at 5+ occurrences
        
        # Factor in recency
        recency_score = self._calculate_recency_score(sorted_tasks)
        
        # Combine scores
        confidence_score = (consistency_score * 0.5 + occurrence_score * 0.3 + recency_score * 0.2)
        
        return {
            'confidence_score': confidence_score,
            'interval_days': int(median_interval),
            'mean_interval': mean_interval,
            'std_interval': std_interval,
            'occurrences': len(tasks),
            'consistency_score': consistency_score,
            'occurrence_score': occurrence_score,
            'recency_score': recency_score
        }
    
    def _calculate_consistency_score(self, intervals: List[float]) -> float:
        """Calculate consistency score based on interval variance"""
        if len(intervals) < 2:
            return 0.0
        
        # Lower variance = higher consistency
        cv = np.std(intervals) / np.mean(intervals) if np.mean(intervals) > 0 else 1.0
        
        # Convert coefficient of variation to consistency score
        # CV < 0.2 = high consistency (0.8-1.0)
        # CV 0.2-0.5 = medium consistency (0.4-0.8)
        # CV > 0.5 = low consistency (0.0-0.4)
        if cv < 0.2:
            return 0.8 + (0.2 - cv) * 1.0  # Scale to 0.8-1.0
        elif cv < 0.5:
            return 0.4 + (0.5 - cv) * 1.33  # Scale to 0.4-0.8
        else:
            return max(0.0, 0.4 - (cv - 0.5) * 0.8)  # Scale to 0.0-0.4
    
    def _calculate_recency_score(self, tasks: List[Task]) -> float:
        """Calculate recency score based on how recent the tasks are"""
        if not tasks:
            return 0.0
        
        # Get the most recent task
        most_recent = max(tasks, key=lambda t: t.created_at)
        days_since_last = (datetime.now() - most_recent.created_at).days
        
        # Higher score for more recent tasks
        if days_since_last <= 7:
            return 1.0
        elif days_since_last <= 30:
            return 0.8
        elif days_since_last <= 90:
            return 0.6
        elif days_since_last <= 180:
            return 0.4
        else:
            return 0.2
    
    def update_task_confidence_scores(self) -> int:
        """Update confidence scores for all tasks based on recurrence analysis"""
        recurring_tasks = self.detect_recurring_tasks()
        updated_count = 0
        
        for recurrence_data in recurring_tasks:
            task_name = recurrence_data['name']
            recurrence_info = recurrence_data['recurrence_info']
            
            # Update all tasks with this name
            tasks_to_update = self.db.query(Task).filter(
                Task.name == task_name,
                Task.is_active == True
            ).all()
            
            for task in tasks_to_update:
                task.confidence_score = recurrence_info['confidence_score']
                if recurrence_info['interval_days']:
                    task.is_recurring = True
                    task.interval_days = recurrence_info['interval_days']
            
            updated_count += len(tasks_to_update)
        
        self.db.commit()
        return updated_count
    
    def detect_recurring_subscriptions(self) -> List[Dict[str, Any]]:
        """Detect recurring subscriptions from transactions (legacy method)"""
        # Get all transactions
        transactions = self.db.query(Transaction).all()
        
        if not transactions:
            return []
        
        # Group by merchant
        merchant_groups = defaultdict(list)
        for transaction in transactions:
            merchant_groups[transaction.merchant].append(transaction)
        
        recurring_subscriptions = []
        
        for merchant, merchant_transactions in merchant_groups.items():
            if len(merchant_transactions) >= 2:
                recurrence_info = self._analyze_transaction_recurrence(merchant_transactions)
                
                if recurrence_info['confidence_score'] > 0.3:
                    recurring_subscriptions.append({
                        'merchant': merchant,
                        'transactions': merchant_transactions,
                        'recurrence_info': recurrence_info
                    })
        
        return recurring_subscriptions
    
    def _analyze_transaction_recurrence(self, transactions: List[Transaction]) -> Dict[str, Any]:
        """Analyze recurrence pattern for a group of transactions"""
        if len(transactions) < 2:
            return {'confidence_score': 0.0, 'interval_days': None}
        
        # Sort transactions by date
        sorted_transactions = sorted(transactions, key=lambda t: t.date)
        
        # Calculate intervals between transactions
        intervals = []
        for i in range(1, len(sorted_transactions)):
            interval = (sorted_transactions[i].date - sorted_transactions[i-1].date).days
            intervals.append(interval)
        
        if not intervals:
            return {'confidence_score': 0.0, 'interval_days': None}
        
        # Calculate statistics
        median_interval = np.median(intervals)
        std_interval = np.std(intervals)
        mean_interval = np.mean(intervals)
        
        # Calculate confidence score
        consistency_score = self._calculate_consistency_score(intervals)
        occurrence_score = min(len(transactions) / 5.0, 1.0)
        recency_score = self._calculate_transaction_recency_score(sorted_transactions)
        
        confidence_score = (consistency_score * 0.5 + occurrence_score * 0.3 + recency_score * 0.2)
        
        return {
            'confidence_score': confidence_score,
            'interval_days': int(median_interval),
            'mean_interval': mean_interval,
            'std_interval': std_interval,
            'occurrences': len(transactions),
            'consistency_score': consistency_score,
            'occurrence_score': occurrence_score,
            'recency_score': recency_score
        }
    
    def _calculate_transaction_recency_score(self, transactions: List[Transaction]) -> float:
        """Calculate recency score for transactions"""
        if not transactions:
            return 0.0
        
        # Get the most recent transaction
        most_recent = max(transactions, key=lambda t: t.date)
        days_since_last = (datetime.now() - most_recent.date).days
        
        # Higher score for more recent transactions
        if days_since_last <= 7:
            return 1.0
        elif days_since_last <= 30:
            return 0.8
        elif days_since_last <= 90:
            return 0.6
        elif days_since_last <= 180:
            return 0.4
        else:
            return 0.2
    
    def generate_recurrence_report(self) -> Dict[str, Any]:
        """Generate a comprehensive recurrence analysis report"""
        recurring_tasks = self.detect_recurring_tasks()
        recurring_subscriptions = self.detect_recurring_subscriptions()
        
        # Calculate summary statistics
        total_recurring_tasks = len(recurring_tasks)
        total_recurring_subscriptions = len(recurring_subscriptions)
        
        # Calculate average confidence scores
        task_confidence_scores = [r['recurrence_info']['confidence_score'] for r in recurring_tasks]
        subscription_confidence_scores = [r['recurrence_info']['confidence_score'] for r in recurring_subscriptions]
        
        avg_task_confidence = np.mean(task_confidence_scores) if task_confidence_scores else 0.0
        avg_subscription_confidence = np.mean(subscription_confidence_scores) if subscription_confidence_scores else 0.0
        
        return {
            'recurring_tasks_count': total_recurring_tasks,
            'recurring_subscriptions_count': total_recurring_subscriptions,
            'average_task_confidence': avg_task_confidence,
            'average_subscription_confidence': avg_subscription_confidence,
            'recurring_tasks': recurring_tasks,
            'recurring_subscriptions': recurring_subscriptions,
            'generated_at': datetime.now().isoformat()
        }
