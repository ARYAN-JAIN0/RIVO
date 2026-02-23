#!/usr/bin/env python
"""Check existing users and create a test user if needed."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.db import get_db_session
from app.database.models import User, Tenant
from app.core.security import hash_password
from app.core.config import get_config

def main():
    cfg = get_config()
    
    with get_db_session() as session:
        # Check tenants
        tenants = session.query(Tenant).all()
        print(f"Tenants: {[(t.id, t.name) for t in tenants]}")
        
        # Check users
        users = session.query(User).all()
        print(f"Users: {[(u.id, u.email, u.role, u.is_active) for u in users]}")
        
        # Reset admin password for testing
        admin = session.query(User).filter(User.email == "admin@example.com").first()
        if admin:
            new_password = "admin123"
            admin.hashed_password = hash_password(new_password, pepper=cfg.PASSWORD_PEPPER)
            session.commit()
            print(f"\nReset password for admin@example.com to: {new_password}")
        else:
            # Create admin user
            hashed_pw = hash_password("admin123", pepper=cfg.PASSWORD_PEPPER)
            admin = User(
                email="admin@example.com",
                hashed_password=hashed_pw,
                role="admin",
                tenant_id=1,
                is_active=True,
            )
            session.add(admin)
            session.commit()
            print("\nCreated admin user:")
            print("  Email: admin@example.com")
            print("  Password: admin123")

if __name__ == "__main__":
    main()
