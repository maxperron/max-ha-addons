from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select
from datetime import date

from database import get_session
from models import Transaction, TransactionCreate, TransactionRead, TransactionBase, Category, Account, User

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.post("/", response_model=TransactionRead)
def create_transaction(transaction: TransactionCreate, session: Session = Depends(get_session)):
    db_transaction = Transaction.from_orm(transaction)
    session.add(db_transaction)
    session.commit()
    session.refresh(db_transaction)
    
    # Eager load names for response
    # Or just construct response manually if lazy loading works
    # Using TransactionRead, we interpret names. But standard Read model matches Base.
    # We defined TransactionRead with extra name fields.
    # We need to populate them.
    
    return _populate_transaction_read(db_transaction, session)

@router.get("/", response_model=List[TransactionRead])
def read_transactions(
    skip: int = 0,
    limit: int = 100,
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    session: Session = Depends(get_session)
):
    query = select(Transaction)
    
    if account_id:
        query = query.where(Transaction.account_id == account_id)
    if category_id:
        query = query.where(Transaction.category_id == category_id)
    if start_date:
        query = query.where(Transaction.date >= start_date)
    if end_date:
        query = query.where(Transaction.date <= end_date)
        
    query = query.order_by(Transaction.date.desc()).offset(skip).limit(limit)
    transactions = session.exec(query).all()
    
    return [_populate_transaction_read(t, session) for t in transactions]

@router.get("/{transaction_id}", response_model=TransactionRead)
def read_transaction(transaction_id: int, session: Session = Depends(get_session)):
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _populate_transaction_read(transaction, session)

@router.put("/{transaction_id}", response_model=TransactionRead)
def update_transaction(transaction_id: int, transaction: TransactionBase, session: Session = Depends(get_session)):
    db_transaction = session.get(Transaction, transaction_id)
    if not db_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    transaction_data = transaction.dict(exclude_unset=True)
    for key, value in transaction_data.items():
        setattr(db_transaction, key, value)
        
    session.add(db_transaction)
    session.commit()
    session.refresh(db_transaction)
    return _populate_transaction_read(db_transaction, session)

@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: int, session: Session = Depends(get_session)):
    transaction = session.get(Transaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    session.delete(transaction)
    session.commit()
    return {"ok": True}

def _populate_transaction_read(transaction: Transaction, session: Session) -> TransactionRead:
    # Manual population because SQLModel/Pydantic validation with relationships can be tricky
    # and we want flat strings for the UI table.
    # Note: Accessing transaction.category triggers lazy load if attached to session.
    
    category_name = transaction.category.name if transaction.category else None
    account_name = transaction.account.name if transaction.account else None
    user_name = transaction.user.name if transaction.user else None
    
    return TransactionRead(
        id=transaction.id,
        date=transaction.date,
        amount=transaction.amount,
        description=transaction.description,
        category_id=transaction.category_id,
        account_id=transaction.account_id,
        user_id=transaction.user_id,
        category_name=category_name,
        account_name=account_name,
        user_name=user_name,
        is_family=transaction.is_family
    )
