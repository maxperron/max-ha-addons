from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from datetime import date

# User (Family Member)
class UserBase(SQLModel):
    name: str = Field(index=True)

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    accounts: List["Account"] = Relationship(back_populates="user")

class UserCreate(UserBase):
    pass

class UserRead(UserBase):
    id: int

# Account
class AccountBase(SQLModel):
    name: str
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    is_shared: bool = False

class Account(AccountBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    user: Optional[User] = Relationship(back_populates="accounts")

class AccountCreate(AccountBase):
    pass

class AccountRead(AccountBase):
    id: int
    user_name: Optional[str] = None # Enriched field

# Category
class CategoryBase(SQLModel):
    name: str
    icon: Optional[str] = None # Emoji or icon name
    parent_id: Optional[int] = Field(default=None, foreign_key="category.id")

class Category(CategoryBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    parent: Optional["Category"] = Relationship(back_populates="subcategories", sa_relationship_kwargs={"remote_side": "Category.id"})
    subcategories: List["Category"] = Relationship(back_populates="parent")

class CategoryCreate(CategoryBase):
    pass

class CategoryRead(CategoryBase):
    id: int


# Transaction Models
class TransactionBase(SQLModel):
    date: date
    amount: float
    description: str
    category_id: int = Field(foreign_key="category.id")
    account_id: int = Field(foreign_key="account.id")
    user_id: Optional[int] = Field(default=None, foreign_key="user.id") # Optional: who made the transaction
    is_family: bool = False

class Transaction(TransactionBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relationships
    category: Optional["Category"] = Relationship()
    account: Optional["Account"] = Relationship()
    user: Optional["User"] = Relationship()

class TransactionCreate(TransactionBase):
    pass

class TransactionUpdate(SQLModel):
    date: Optional[date] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    account_id: Optional[int] = None
    user_id: Optional[int] = None
    is_family: Optional[bool] = None

class TransactionRead(TransactionBase):
    id: int
    category_name: Optional[str] = None
    account_name: Optional[str] = None
    user_name: Optional[str] = None


# Import Rules
class ImportRuleBase(SQLModel):
    pattern: str  # Keywords to match in description
    category_id: int = Field(foreign_key="category.id")
    # match_type: str = "contains" # future: exact, regex?

class ImportRule(ImportRuleBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    category: Optional["Category"] = Relationship()

class ImportRuleCreate(ImportRuleBase):
    pass

class ImportRuleRead(ImportRuleBase):
    id: int
    category_name: Optional[str] = None
