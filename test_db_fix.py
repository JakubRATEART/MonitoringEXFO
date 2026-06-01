#!/usr/bin/env python3
"""
Test script to verify database insertion works correctly after SQL fix.
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'devices.db')

def test_insertion():
    """Test the fixed SQL insertion logic"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Test data matching what the PDF extraction would provide
    test_data = [
        ('T-72C+', '1.32', '9 Jul, 2025'),
        ('T-57C+', '1.10', '18 Dec, 2025'),
        ('T-502S', '1.16', '9 Apr, 2026'),
    ]

    print("Testing database insertion with fixed SQL...")
    for model, version, release_date in test_data:
        now = datetime.now().strftime("%Y-%m-%d")
        try:
            # This is the FIXED SQL from pdf_scheduler.py
            cur.execute(
                """
                INSERT INTO devices (model, stored_version, stored_release_date, last_checked)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(model) DO UPDATE SET
                    stored_version = excluded.stored_version,
                    stored_release_date = excluded.stored_release_date,
                    last_checked = excluded.last_checked
                """,
                (model, version, release_date, now)
            )
            print(f"  ✓ Inserted {model} v{version}")
        except Exception as e:
            print(f"  ✗ Failed to insert {model}: {e}")
            return False

    conn.commit()

    # Verify data was inserted
    print("\nVerifying inserted data...")
    cur.execute('SELECT model, stored_version, stored_release_date, last_checked FROM devices WHERE model IN (?, ?, ?)',
                ('T-72C+', 'T-57C+', 'T-502S'))
    rows = cur.fetchall()

    if len(rows) == 3:
        print(f"  ✓ Successfully inserted {len(rows)} records")
        for row in rows:
            print(f"    - {row[0]}: v{row[1]} ({row[2]}) [checked: {row[3]}]")
        return True
    else:
        print(f"  ✗ Expected 3 records, got {len(rows)}")
        return False

    conn.close()

if __name__ == '__main__':
    if test_insertion():
        print("\n✅ Database fix verified successfully!")
        print("\nNow you can:")
        print("  1. Run the scheduler: pdf_scheduler.start()")
        print("  2. Call /api/refresh endpoint to manually trigger extraction")
        print("  3. Check database: sqlite3 devices.db '.mode column' '.headers on' 'SELECT * FROM devices;'")
    else:
        print("\n❌ Database test failed!")
