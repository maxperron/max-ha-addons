from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select, SQLModel
from datetime import date

from database import get_session
from models import Transaction, TransactionCreate, TransactionRead, TransactionUpdate, TransactionBase, Category, Account, User

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

@router.get("/ai-test")
def test_ai_connection(session: Session = Depends(get_session)):
    from models import Setting
    import google.generativeai as genai
    
    api_key_setting = session.get(Setting, "gemini_api_key")
    if not api_key_setting or not api_key_setting.value:
        raise HTTPException(status_code=400, detail="Gemini API Key not configured.")
        
    genai.configure(api_key=api_key_setting.value)
    
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")
        
    return {
        "status": "ok",
        "available_models": available_models,
        "message": f"Connection successful. Found {len(available_models)} models."
    }


@router.get("/", response_model=List[TransactionRead])
def read_transactions(
    skip: int = 0,
    limit: int = 100,
    account_id: Optional[int] = None,
    category_id: Optional[int] = None,
    trip_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    session: Session = Depends(get_session)
):
    query = select(Transaction)
    
    if account_id:
        query = query.where(Transaction.account_id == account_id)
    if category_id:
        query = query.where(Transaction.category_id == category_id)
    if trip_id:
        query = query.where(Transaction.trip_id == trip_id)
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
def update_transaction(transaction_id: int, transaction: TransactionUpdate, session: Session = Depends(get_session)):
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
    trip_name = transaction.trip.name if transaction.trip else None
    
    return TransactionRead(
        id=transaction.id,
        date=transaction.date,
        amount=transaction.amount,
        description=transaction.description,
        category_id=transaction.category_id,
        account_id=transaction.account_id,
        user_id=transaction.user_id,
        trip_id=transaction.trip_id,
        category_name=category_name,
        account_name=account_name,
        user_name=user_name,
        trip_name=trip_name,
        is_family=transaction.is_family
    )

class AICategorizeRequest(SQLModel):
    transaction_ids: List[int]

@router.post("/ai-categorize")
def ai_categorize_transactions(request: AICategorizeRequest, session: Session = Depends(get_session)):
    # 1. Get API Key
    from models import Setting, ImportRule
    import google.generativeai as genai
    import json
    
    api_key_setting = session.get(Setting, "gemini_api_key")
    if not api_key_setting or not api_key_setting.value:
        raise HTTPException(status_code=400, detail="Gemini API Key not configured in Settings.")
        
    genai.configure(api_key=api_key_setting.value)
    
    # 2. Get Data
    categories = session.exec(select(Category)).all()
    categories_str = "\n".join([f"{c.id}: {c.name}" for c in categories])
    
    transactions = []
    for tid in request.transaction_ids:
        t = session.get(Transaction, tid)
        if t: transactions.append(t)
        
    if not transactions:
        return {"processed": 0, "message": "No transactions found."}
        
    transactions_str = "\n".join([f"{t.id}: {t.description} (${t.amount})" for t in transactions])
    
    # 3. Construct Prompt
    prompt = f"""
You are a helpful personal finance assistant.
Your task is to categorize the following transactions based on the provided categories.
You should also suggest a 'rule_pattern' to auto-categorize similar transactions in the future (e.g. for 'Starbucks #123' use 'Starbucks').

Categories:
{categories_str}

Transactions:
{transactions_str}

Return a generic JSON list of objects. Each object must have:
- "id": (int) the transaction id
- "category_id": (int) the matched category id, or null if absolutely unsure.
- "rule_pattern": (string) a keyword/substring to match this merchant, or null if generic.

Respond ONLY with the JSON list.
"""

    # 4. Call Model
    models_to_try = ['gemini-2.0-flash', 'gemini-2.0-flash-exp', 'gemini-1.5-flash', 'gemini-1.5-flash-001', 'gemini-pro']
    model = None
    response = None
    last_error = None

    for model_name in models_to_try:
        try:
            print(f"Attempting AI categorization with model: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            print(f"Success with model: {model_name}")
            break
        except Exception as e:
            print(f"Failed with {model_name}: {e}")
            last_error = e
    
    if not response:
         raise HTTPException(status_code=500, detail=f"AI Processing Failed. Tried models {models_to_try}. Last error: {str(last_error)}")

    try:
        text_response = response.text
        
        # Cleanup markdown
        if "```json" in text_response:
             text_response = text_response.split("```json")[1].split("```")[0]
        elif "```" in text_response:
             text_response = text_response.split("```")[1].split("```")[0]
             
        results = json.loads(text_response)
        
    except Exception as e:
        print(f"AI Response Parsing Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI Response Parsing Failed: {str(e)}")
        
    # 5. Process Results
    updated_count = 0
    rules_created = 0
    
    for res in results:
        tid = res.get("id")
        cid = res.get("category_id")
        pattern = res.get("rule_pattern")
        
        if not tid: continue
        
        # Update Transaction
        if cid:
            t = session.get(Transaction, tid)
            if t:
                t.category_id = cid
                session.add(t)
                updated_count += 1
                
        # Create Rule (if pattern provided and cid provided)
        if pattern and cid:
            # Check duplicate rule
            existing = session.exec(select(ImportRule).where(ImportRule.pattern == pattern)).first()
            if not existing:
                new_rule = ImportRule(pattern=pattern, category_id=cid)
                session.add(new_rule)
                rules_created += 1
                
    session.commit()
    
    return {
        "processed": len(transactions),
        "updated": updated_count,
        "new_rules": rules_created,
        "message": f"AI categorized {updated_count} transactions and created {rules_created} new rules."
    }

