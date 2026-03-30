#!/usr/bin/env python
"""
Simple database initialization script
Run this from the project root: python init.py
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import Base, engine
from app.models.user import User
from app.models.video import Video
from app.models.roi import ROI
from app.models.analysis_run import AnalysisRun
from app.models.violation import Violation
from app.models.report import Report
from app.core.security import get_password_hash
from sqlalchemy.orm import Session

def init_database():
    """Create all tables and seed initial data"""
    
    print("Creating database tables...")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("✅ Tables created successfully!")
    
    # Create a session
    db = Session(engine)
    
    try:
        # Check if admin user exists
        admin = db.query(User).filter(User.email == "admin@cypath.com").first()
        
        if not admin:
            print("Creating admin user...")
            admin_user = User(
                full_name="System Administrator",
                email="admin@cypath.com",
                password_hash=get_password_hash("admin123"),
                role="ADMIN",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("✅ Admin user created! (email: admin@cypath.com, password: admin123)")
        else:
            print("✅ Admin user already exists")
        
        # Optional: Create a test user for development
        test_user = db.query(User).filter(User.email == "test@cypath.com").first()
        if not test_user:
            print("Creating test user...")
            test_user = User(
                full_name="Test Analyst",
                email="test@cypath.com",
                password_hash=get_password_hash("test123"),
                role="ANALYST",
                is_active=True
            )
            db.add(test_user)
            db.commit()
            print("✅ Test user created! (email: test@cypath.com, password: test123)")
        
    except Exception as e:
        print(f"❌ Error creating users: {e}")
        db.rollback()
    finally:
        db.close()
    
    print("\n🎉 Database initialization complete!")
    print("\nYou can now run the server with:")
    print("uvicorn app.main:app --reload")

if __name__ == "__main__":
    init_database()