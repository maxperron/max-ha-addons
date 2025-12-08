from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlmodel import Session, select
import csv
import codecs
from datetime import datetime

from database import get_session
from models import ImportRule, ImportRuleCreate, ImportRuleRead, Category, Transaction, TransactionCreate, TransactionRead, Account

router = APIRouter(prefix="/imports", tags=["imports"])

@router.post("/rules/", response_model=ImportRuleRead)
def create_rule(rule: ImportRuleCreate, session: Session = Depends(get_session)):
    db_rule = ImportRule.from_orm(rule)
    session.add(db_rule)
    session.commit()
    session.refresh(db_rule)
    return _populate_rule_read(db_rule, session)

@router.get("/rules/", response_model=List[ImportRuleRead])
def read_rules(session: Session = Depends(get_session)):
    rules = session.exec(select(ImportRule)).all()
    return [_populate_rule_read(r, session) for r in rules]

@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, session: Session = Depends(get_session)):
    rule = session.get(ImportRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()
    return {"ok": True}

@router.post("/upload")
async def upload_csv(
    account_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """
    Parses a CSV file and creates transactions.
    Auto-categorizes based on rules.
    Expected CSV columns: Date, Description, Amount
    """
    if not account_id:
        raise HTTPException(status_code=400, detail="Account ID required")
        
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    # Load all rules for matching
    rules = session.exec(select(ImportRule)).all()
    
    # Read file
    content = await file.read()
    decoded = content.decode("utf-8-sig") # handle BOM
    reader = csv.DictReader(codecs.iterdecode(decoded.splitlines(), "utf-8"))
    
    # Normalize headers roughly? 
    # Let's assume standard headers for now or try to detect.
    # Simple strategy: look for 'date', 'amount', 'description' case-insensitive.
    
    transactions_created = 0
    
    # We need to map CSV headers to our fields
    # This is brittle without a mapping UI, but let's try standard names.
    
    csv_lines = list(csv.reader(decoded.splitlines()))
    if not csv_lines:
        return {"count": 0}
        
    headers = [h.lower() for h in csv_lines[0]]
    
    # Simple Index detection
    try:
        date_idx = -1
        desc_idx = -1
        amount_idx = -1
        
        for i, h in enumerate(headers):
            if 'date' in h: date_idx = i
            if 'description' in h or 'memo' in h or 'payee' in h: desc_idx = i
            if 'amount' in h: amount_idx = i
            
        if date_idx == -1 or amount_idx == -1:
             raise HTTPException(status_code=400, detail="Could not find 'Date' or 'Amount' columns in CSV.")
             
        # Skip header
        for row in csv_lines[1:]:
            if len(row) < max(date_idx, desc_idx, amount_idx): continue
            
            raw_date = row[date_idx]
            raw_desc = row[desc_idx] if desc_idx != -1 else "Imported Transaction"
            raw_amount = row[amount_idx]
            
            # Parsing Date
            # Try formats YYYY-MM-DD, MM/DD/YYYY, etc. 
            # Very basic parser: assuming ISO or MM/DD/YYYY
            try:
                parsed_date = _parse_date(raw_date)
            except:
                continue # skip bad dates
                
            # Parsing Amount
            try:
                # Remove currency symbols, commas
                clean_amount = raw_amount.replace('$', '').replace(',', '')
                amount = float(clean_amount)
            except:
                continue
                
            # Rule Engine
            category_id = _apply_rules(raw_desc, rules)
            
            # Create Transaction
            # If no category match, what to do? 
            # Require category_id in DB? Yes.
            # So either fail or assign "Uncategorized"?
            # We need a fallback category or allow NULL in DB? Model says category_id is int (required).
            # Let's find or create "Uncategorized"?
            # For now, if no category, maybe pick the first one or a default?
            # Creating a default category if match fails is risky.
            # Better: Make category_id optional in Transaction?
            # Or find a category named "Uncategorized" or "General".
            
            final_category_id = category_id
            if not final_category_id:
                # Fallback: check if "Uncategorized" exists, else create it?
                # Or just error? users might hate that.
                # Let's try to find any category.
                uncat = session.exec(select(Category).where(Category.name == "Uncategorized")).first()
                if not uncat:
                    # Create it ?
                    uncat = Category(name="Uncategorized", icon="❓")
                    session.add(uncat)
                    session.commit()
                    session.refresh(uncat)
                final_category_id = uncat.id

            transaction = Transaction(
                date=parsed_date,
                amount=amount,
                description=raw_desc,
                account_id=account_id,
                category_id=final_category_id
            )
            session.add(transaction)
            transactions_created += 1
            
        session.commit()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")

    return {"count": transactions_created, "message": f"Successfully imported {transactions_created} transactions."}

def _parse_date(date_str: str) -> datetime.date:
    # Try multiple formats
    date_str = date_str.strip()
    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    raise ValueError("Unknown date format")

def _apply_rules(description: str, rules: List[ImportRule]) -> Optional[int]:
    """Returns matching category_id or None"""
    description_lower = description.lower()
    for rule in rules:
        if rule.pattern.lower() in description_lower:
            return rule.category_id
    return None

def _populate_rule_read(rule: ImportRule, session: Session) -> ImportRuleRead:
    category_name = rule.category.name if rule.category else None
    return ImportRuleRead(
        id=rule.id,
        pattern=rule.pattern,
        category_id=rule.category_id,
        category_name=category_name
    )
