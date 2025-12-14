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
        # Enable Foreign Keys
        session.exec(text("PRAGMA foreign_keys = ON"))

        # 1. Create User table
        try:
            tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")).all()
            if not tables:
                session.exec(text("CREATE TABLE IF NOT EXISTS user (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"))
                session.commit()
                print("Migrated: Created user table (Manual)")
        except Exception as e:
            print(f"Migration User Failed: {e}")

        # 2. Create Category table
        try:
            tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='category'")).all()
            if not tables:
                session.exec(text("CREATE TABLE IF NOT EXISTS category (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, icon TEXT, parent_id INTEGER, FOREIGN KEY(parent_id) REFERENCES category(id))"))
                session.commit()
                print("Migrated: Created category table (Manual)")
        except Exception as e:
            print(f"Migration Category Failed: {e}")

        # 3. Create Trip table
        try:
            tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='trip'")).all()
            if not tables:
                session.exec(text("CREATE TABLE IF NOT EXISTS trip (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"))
                session.commit()
                print("Migrated: Created trip table (Manual)")
        except Exception as e:
            print(f"Migration Trip Failed: {e}")

        # 4. Create Account table
        try:
            tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='account'")).all()
            if not tables:
                session.exec(text("CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, user_id INTEGER, is_shared BOOLEAN DEFAULT 0, FOREIGN KEY(user_id) REFERENCES user(id))"))
                session.commit()
                print("Migrated: Created account table (Manual)")
        except Exception as e:
            print(f"Migration Account Failed: {e}")

        # 5. Create Transaction table
        try:
            tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='transaction'")).all()
            if not tables:
                session.exec(text("""
                    CREATE TABLE IF NOT EXISTS "transaction" (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, 
                        date DATE, 
                        amount FLOAT, 
                        description TEXT, 
                        category_id INTEGER, 
                        account_id INTEGER, 
                        user_id INTEGER, 
                        trip_id INTEGER, 
                        is_family BOOLEAN DEFAULT 0,
                        FOREIGN KEY(category_id) REFERENCES category(id),
                        FOREIGN KEY(account_id) REFERENCES account(id),
                        FOREIGN KEY(user_id) REFERENCES user(id),
                        FOREIGN KEY(trip_id) REFERENCES trip(id)
                    )
                """))
                session.commit()
                print("Migrated: Created transaction table (Manual)")
        except Exception as e:
            print(f"Migration Transaction Failed: {e}")

        # 6. Create Setting table
        try:
            tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='setting'")).all()
            if not tables:
                session.exec(text("CREATE TABLE IF NOT EXISTS setting (key TEXT PRIMARY KEY, value TEXT)"))
                session.commit()
                print("Migrated: Created setting table (Manual)")
        except Exception as e:
            print(f"Migration Setting Failed: {e}")

        # 7. Create ImportRule table
        try:
            tables = session.exec(text("SELECT name FROM sqlite_master WHERE type='table' AND name='importrule'")).all()
            if not tables:
                session.exec(text("CREATE TABLE IF NOT EXISTS importrule (id INTEGER PRIMARY KEY AUTOINCREMENT, pattern TEXT NOT NULL, category_id INTEGER NOT NULL, FOREIGN KEY(category_id) REFERENCES category(id))"))
                session.commit()
                print("Migrated: Created importrule table (Manual)")
        except Exception as e:
            print(f"Migration ImportRule Failed: {e}")

        # --- Alterations for existing tables (Backwards Compatibility) ---

        # Add parent_id to category if missing
        try:
            columns = session.exec(text("PRAGMA table_info(category)")).all()
            if columns:
                col_names = [c.name for c in columns]
                if 'parent_id' not in col_names:
                    session.exec(text("ALTER TABLE category ADD COLUMN parent_id INTEGER"))
                    session.commit()
                    print("Migrated: Added parent_id to category")
        except Exception as e:
            print(f"Migration Alter Category Failed: {e}")

        # Add is_shared to account if missing
        try:
            columns = session.exec(text("PRAGMA table_info(account)")).all()
            if columns:
                col_names = [c.name for c in columns]
                if 'is_shared' not in col_names:
                    session.exec(text("ALTER TABLE account ADD COLUMN is_shared BOOLEAN DEFAULT 0"))
                    session.commit()
                    print("Migrated: Added is_shared to account")
        except Exception as e:
            print(f"Migration Alter Account Failed: {e}")

        # Add is_family and trip_id to transaction if missing
        try:
            columns = session.exec(text("PRAGMA table_info('transaction')")).all()
            if columns:
                col_names = [c.name for c in columns]
                if 'is_family' not in col_names:
                    session.exec(text("ALTER TABLE 'transaction' ADD COLUMN is_family BOOLEAN DEFAULT 0"))
                    session.commit()
                    print("Migrated: Added is_family to transaction")
                if 'trip_id' not in col_names:
                    session.exec(text("ALTER TABLE 'transaction' ADD COLUMN trip_id INTEGER"))
                    session.commit()
                    print("Migrated: Added trip_id to transaction")
        except Exception as e:
            print(f"Migration Alter Transaction Failed: {e}")

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
