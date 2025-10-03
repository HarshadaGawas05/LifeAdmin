#!/usr/bin/env python3
"""
Script to seed the database with sample transaction data from a CSV file.
This simulates importing data from Plaid or other financial data providers.
"""

import csv
import sys
import os
from datetime import datetime, timedelta
import random

# Add the parent directory to the path so we can import from api
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from database import SessionLocal, create_tables
from models import Transaction


def parse_csv_file(csv_file_path: str):
    """Parse a CSV file and return transaction data"""
    transactions = []
    
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                # Parse the transaction data
                transaction = {
                    'merchant': row.get('merchant', 'Unknown'),
                    'amount': float(row.get('amount', 0)),
                    'date': datetime.strptime(row.get('date', ''), '%Y-%m-%d'),
                    'description': row.get('description', ''),
                    'source': 'plaid_csv',
                    'source_details': f'Imported from CSV: {csv_file_path}'
                }
                transactions.append(transaction)
            except (ValueError, KeyError) as e:
                print(f"Error parsing row: {row}, Error: {e}")
                continue
    
    return transactions


def seed_database(transactions):
    """Seed the database with transaction data"""
    db = SessionLocal()
    
    try:
        # Clear existing Plaid CSV data
        db.query(Transaction).filter(Transaction.source == 'plaid_csv').delete()
        
        # Add new transactions
        for transaction_data in transactions:
            transaction = Transaction(**transaction_data)
            db.add(transaction)
        
        db.commit()
        print(f"Successfully seeded {len(transactions)} transactions from CSV")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()


def create_sample_csv():
    """Create a sample CSV file with transaction data"""
    sample_data = [
        {
            'date': '2024-01-15',
            'merchant': 'Netflix',
            'amount': '499.00',
            'description': 'Netflix subscription'
        },
        {
            'date': '2024-02-15',
            'merchant': 'Netflix',
            'amount': '499.00',
            'description': 'Netflix subscription'
        },
        {
            'date': '2024-03-15',
            'merchant': 'Netflix',
            'amount': '499.00',
            'description': 'Netflix subscription'
        },
        {
            'date': '2024-01-20',
            'merchant': 'Spotify',
            'amount': '199.00',
            'description': 'Spotify Premium'
        },
        {
            'date': '2024-02-20',
            'merchant': 'Spotify',
            'amount': '199.00',
            'description': 'Spotify Premium'
        },
        {
            'date': '2024-03-20',
            'merchant': 'Spotify',
            'amount': '199.00',
            'description': 'Spotify Premium'
        },
        {
            'date': '2024-01-25',
            'merchant': 'MSEB Electricity',
            'amount': '1200.00',
            'description': 'Monthly electricity bill'
        },
        {
            'date': '2024-02-25',
            'merchant': 'MSEB Electricity',
            'amount': '1200.00',
            'description': 'Monthly electricity bill'
        },
        {
            'date': '2024-03-25',
            'merchant': 'MSEB Electricity',
            'amount': '1200.00',
            'description': 'Monthly electricity bill'
        },
        {
            'date': '2024-02-10',
            'merchant': 'Amazon',
            'amount': '1500.00',
            'description': 'One-time purchase'
        },
        {
            'date': '2024-03-05',
            'merchant': 'Uber',
            'amount': '250.00',
            'description': 'Ride fare'
        }
    ]
    
    csv_file_path = 'sample_transactions.csv'
    with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
        fieldnames = ['date', 'merchant', 'amount', 'description']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sample_data)
    
    print(f"Created sample CSV file: {csv_file_path}")
    return csv_file_path


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python seed_plaid.py <csv_file_path>")
        print("Or: python seed_plaid.py --create-sample")
        return
    
    if sys.argv[1] == '--create-sample':
        csv_file_path = create_sample_csv()
        print(f"Sample CSV created at: {csv_file_path}")
        return
    
    csv_file_path = sys.argv[1]
    
    if not os.path.exists(csv_file_path):
        print(f"Error: CSV file not found: {csv_file_path}")
        return
    
    # Create database tables
    create_tables()
    
    # Parse CSV and seed database
    transactions = parse_csv_file(csv_file_path)
    if transactions:
        seed_database(transactions)
    else:
        print("No valid transactions found in CSV file")


if __name__ == '__main__':
    main()

