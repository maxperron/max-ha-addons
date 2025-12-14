from sqlmodel import SQLModel, create_engine, Session, select
import os

# Home Assistant addon data directory or local fallback
DATA_DIR = "/data" if os.path.isdir("/data") else "."
DB_NAME = "expenses.db"
DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, DB_NAME)}"

# check_same_thread=False is needed for SQLite with FastAPI multi-threading
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

def create_db_and_tables():
    # Ensure models are registered with SQLModel before creating tables
    import models 
    SQLModel.metadata.create_all(engine)
    migrate_db()
    seed_db()

def migrate_db():
    with Session(engine) as session:
        # Migration 1: Add parent_id to category
        try:
            # Check for column existence
            columns = session.exec(text("PRAGMA table_info(category)")).all()
            col_names = [c.name for c in columns]
            if 'parent_id' not in col_names:
                session.exec(text("ALTER TABLE category ADD COLUMN parent_id INTEGER"))
                session.commit()
                print("Migrated: Added parent_id to category")
        except Exception as e:
            print(f"Migration 1 Failed: {e}")

        # Migration 2: Add is_shared to account
        try:
            columns = session.exec(text("PRAGMA table_info(account)")).all()
            col_names = [c.name for c in columns]
            if 'is_shared' not in col_names:
                session.exec(text("ALTER TABLE account ADD COLUMN is_shared BOOLEAN DEFAULT 0"))
                session.commit()
                print("Migrated: Added is_shared to account")
        except Exception as e:
            print(f"Migration 2 Failed: {e}")

        # Migration 3: Add is_family to transaction
        try:
            # Try 'transaction' table
            table_name = 'transaction'
            columns = session.exec(text(f"PRAGMA table_info('{table_name}')")).all()
            
            # If empty, maybe table doesn't exist yet? (Should exist if user has data)
            # If it exists, check columns
            if columns:
                col_names = [c.name for c in columns]
                if 'is_family' not in col_names:
                    session.exec(text(f"ALTER TABLE '{table_name}' ADD COLUMN is_family BOOLEAN DEFAULT 0"))
                    session.commit()
                    print("Migrated: Added is_family to transaction")
            else:
                print("Migration 3: Transaction table not found in PRAGMA?")

        except Exception as e:
            print(f"Migration 3 Failed: {e}")

        # Migration 4: Create trip table
        try:
            # Check if trip table exists
            tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='trip'")).all()
            if not tables:
                # We can use SQLModel generic creation, but create_all usually only creates tables that don't exist.
                # However, create_all is called at start. So table should be created automatically if we just run checking?
                # Actually create_db_and_tables calls create_all.
                # But for existing DBs, create_all might not update schema if table exists but we want to add columns?
                # Here we are creating a NEW table. SQLModel.metadata.create_all(engine) should handle it.
                # BUT, let's allow create_all to do its job for new tables.
                # The issue is create_all does NOT modify existing tables.
                # So for new table 'trip', create_all is sufficient? Yes.
                # But let's leave this placeholder if we need manual intervention.
                pass
        except Exception as e:
            print(f"Migration 4 Failed: {e}")

        # Migration 5: Add trip_id to transaction
        try:
            table_name = 'transaction'
            columns = session.exec(text(f"PRAGMA table_info('{table_name}')")).all()
            if columns:
                col_names = [c.name for c in columns]
                if 'trip_id' not in col_names:
                    session.exec(text(f"ALTER TABLE '{table_name}' ADD COLUMN trip_id INTEGER"))
                    session.commit()
                    print("Migrated: Added trip_id to transaction")
        except Exception as e:
            print(f"Migration 5 Failed: {e}")

        # Migration 6: Create setting table
        try:
            # Check if setting table exists
            tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='setting'")).all()
            if not tables:
                # Use IF NOT EXISTS for safety
                session.exec(text("CREATE TABLE IF NOT EXISTS setting (key TEXT PRIMARY KEY, value TEXT)"))
                session.commit()
                print("Migrated: Created setting table")
        except Exception as e:
            print(f"Migration 6 Failed: {e}")

def seed_db():
    from models import Category
    with Session(engine) as session:
        if session.exec(select(Category)).first():
            return
        
        # Default Categories from reference app logic
        categories = [
            Category(name="Housing", icon="🏠"),
            Category(name="Food", icon="🍔"),
            Category(name="Transportation", icon="🚗"),
            Category(name="Utilities", icon="💡"),
            Category(name="Insurance", icon="🛡️"),
            Category(name="Medical", icon="💊"),
            Category(name="Saving", icon="💰"),
            Category(name="Personal", icon="👤"),
            Category(name="Entertainment", icon="🎉"),
            Category(name="Miscellaneous", icon="📦"),
        ]
        
        session.add_all(categories)
        session.commit()
        
        # Add some subcategories for demo
        food = session.exec(select(Category).where(Category.name == "Food")).first()
        if food:
            session.add(Category(name="Groceries", icon="🛒", parent_id=food.id))
            session.add(Category(name="Restaurants", icon="🍽️", parent_id=food.id))
            session.commit()

def get_session():
    with Session(engine) as session:
        yield session
