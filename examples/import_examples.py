import json
import os
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from models import RawEmail


def main():
    database_url = os.getenv('DATABASE_URL', 'postgresql://lifeadmin:lifeadmin@localhost:5432/lifeadmin')
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db: Session = SessionLocal()

    folder = os.path.join(os.path.dirname(__file__), 'samples')
    count = 0
    for fname in os.listdir(folder):
        if not fname.endswith('.json'):
            continue
        with open(os.path.join(folder, fname), 'r') as f:
            data = json.load(f)
        existing = db.query(RawEmail).filter(RawEmail.email_id == data['id']).first()
        if existing:
            continue
        sent_at = None
        try:
            sent_at = datetime.strptime(data.get('date', ''), '%Y-%m-%dT%H:%M:%SZ') if data.get('date') else None
        except Exception:
            pass
        db.add(RawEmail(
            email_id=data['id'],
            thread_id=data.get('threadId'),
            subject=data.get('subject'),
            sender=data.get('sender'),
            sent_at=sent_at,
            snippet=(data.get('body') or '')[:500],
            raw_payload=data
        ))
        count += 1
    db.commit()
    print(f"Imported {count} example emails")


if __name__ == '__main__':
    main()


