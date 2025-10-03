import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os

from models import Base, Transaction, RecurringSubscription
from recurrence_detector import RecurrenceDetector


@pytest.fixture
def db_session():
    """Create a test database session"""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def sample_transactions(db_session):
    """Create sample transactions for testing"""
    base_date = datetime.now() - timedelta(days=90)
    
    # Netflix transactions (monthly)
    for month in range(3):
        transaction = Transaction(
            merchant="Netflix",
            amount=499.0,
            date=base_date + timedelta(days=month * 30),
            description="Netflix subscription",
            source="mock",
            source_details="Test data"
        )
        db_session.add(transaction)
    
    # Spotify transactions (monthly)
    for month in range(3):
        transaction = Transaction(
            merchant="Spotify",
            amount=199.0,
            date=base_date + timedelta(days=month * 30 + 5),
            description="Spotify Premium",
            source="mock",
            source_details="Test data"
        )
        db_session.add(transaction)
    
    # MSEB transactions (monthly)
    for month in range(3):
        transaction = Transaction(
            merchant="MSEB Electricity",
            amount=1200.0,
            date=base_date + timedelta(days=month * 30 + 10),
            description="Electricity bill",
            source="mock",
            source_details="Test data"
        )
        db_session.add(transaction)
    
    # One-time transaction (should not be detected as recurring)
    transaction = Transaction(
        merchant="Amazon",
        amount=1500.0,
        date=base_date + timedelta(days=15),
        description="One-time purchase",
        source="mock",
        source_details="Test data"
    )
    db_session.add(transaction)
    
    db_session.commit()
    return db_session.query(Transaction).all()


def test_recurrence_detection(db_session, sample_transactions):
    """Test that recurrence detection finds at least 3 subscriptions"""
    detector = RecurrenceDetector(db_session)
    detected_subscriptions = detector.detect_recurring_subscriptions()
    
    # Should detect at least 3 recurring subscriptions
    assert len(detected_subscriptions) >= 3
    
    # Check that we found the expected merchants
    merchants = [sub.merchant for sub in detected_subscriptions]
    assert "Netflix" in merchants
    assert "Spotify" in merchants
    assert "MSEB Electricity" in merchants
    
    # Check that Amazon is not detected as recurring (only one transaction)
    assert "Amazon" not in merchants


def test_confidence_scores(db_session, sample_transactions):
    """Test that confidence scores are calculated correctly"""
    detector = RecurrenceDetector(db_session)
    detected_subscriptions = detector.detect_recurring_subscriptions()
    
    for subscription in detected_subscriptions:
        # Confidence should be between 0 and 1
        assert 0.0 <= subscription.confidence_score <= 1.0
        
        # For our test data with 3 consistent transactions, confidence should be high
        assert subscription.confidence_score >= 0.5


def test_interval_calculation(db_session, sample_transactions):
    """Test that intervals are calculated correctly"""
    detector = RecurrenceDetector(db_session)
    detected_subscriptions = detector.detect_recurring_subscriptions()
    
    for subscription in detected_subscriptions:
        # Monthly subscriptions should have intervals around 30 days
        assert 23 <= subscription.interval_days <= 37


def test_source_transparency(db_session, sample_transactions):
    """Test that source transparency information is created"""
    detector = RecurrenceDetector(db_session)
    detected_subscriptions = detector.detect_recurring_subscriptions()
    
    for subscription in detected_subscriptions:
        # Source transparency should not be empty
        assert subscription.source_transparency
        assert len(subscription.source_transparency) > 0
        
        # Should contain information about the source
        assert "Mock data" in subscription.source_transparency or "mock" in subscription.source_transparency.lower()


def test_next_due_date_calculation(db_session, sample_transactions):
    """Test that next due dates are calculated correctly"""
    detector = RecurrenceDetector(db_session)
    detected_subscriptions = detector.detect_recurring_subscriptions()
    
    for subscription in detected_subscriptions:
        # Next due date should be after last paid date
        assert subscription.next_due_date > subscription.last_paid_date
        
        # Next due date should be approximately one interval after last paid date
        expected_next_due = subscription.last_paid_date + timedelta(days=subscription.interval_days)
        time_diff = abs((subscription.next_due_date - expected_next_due).days)
        assert time_diff <= 1  # Allow 1 day difference for rounding

