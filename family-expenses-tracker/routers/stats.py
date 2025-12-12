from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select, func, desc, extract
from datetime import date, datetime, timedelta
from database import get_session
from models import Transaction, Category, User, Trip, Account

router = APIRouter(prefix="/stats", tags=["stats"])

@router.get("/dashboard")
def get_dashboard_stats(
    year: int = Query(..., description="Year filter"),
    month: int = Query(..., description="Month filter"),
    scope: str = Query("all", description="'all', 'family', 'personal', or user_id"),
    session: Session = Depends(get_session)
):
    # Determine date range for the selected month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
        
    # Determine date range for previous month (for comparison)
    prev_month_date = start_date - timedelta(days=1)
    prev_month_start = date(prev_month_date.year, prev_month_date.month, 1)
    prev_month_end = start_date - timedelta(days=1)
    
    # Base Query Builder
    def apply_scope(query):
        if scope == "family":
            return query.where(Transaction.is_family == True)
        elif scope == "personal":
             return query.where(Transaction.is_family == False)
        elif scope != "all":
            # Assuming scope is a user_id
            try:
                user_id = int(scope)
                return query.where(Transaction.user_id == user_id)
            except ValueError:
                return query
        return query

    # 1. Current Month Total
    q_curr = select(func.sum(Transaction.amount)).where(Transaction.date >= start_date).where(Transaction.date <= end_date)
    q_curr = apply_scope(q_curr)
    curr_total = session.exec(q_curr).one() or 0.0
    
    # 2. Last Month Total
    q_prev = select(func.sum(Transaction.amount)).where(Transaction.date >= prev_month_start).where(Transaction.date <= prev_month_end)
    q_prev = apply_scope(q_prev)
    prev_total = session.exec(q_prev).one() or 0.0
    
    # 3. Category Breakdown (Current Month)
    # Group by category, order by total desc
    q_cat = select(Transaction.category_id, Category.name, func.sum(Transaction.amount).label("total"))\
        .join(Category, isouter=True)\
        .where(Transaction.date >= start_date).where(Transaction.date <= end_date)
    q_cat = apply_scope(q_cat)
    q_cat = q_cat.group_by(Transaction.category_id, Category.name).order_by(desc("total"))
    
    cat_results = session.exec(q_cat).all()
    categories = [{"id": r[0], "name": r[1] or "Uncategorized", "total": r[2]} for r in cat_results]
    
    # 4. Trend (Last 6 Months)
    # This is a bit more complex in pure SQLModel without raw SQL, doing a loop for simplicity and portability
    trend = []
    # Start from 5 months ago
    trend_start = start_date
    for i in range(5):
        trend_start = (trend_start.replace(day=1) - timedelta(days=1)).replace(day=1)
    
    # Loop from trend_start to current month
    iter_date = trend_start
    while iter_date <= start_date:
        # Define month range
        if iter_date.month == 12:
            m_end = date(iter_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            m_end = date(iter_date.year, iter_date.month + 1, 1) - timedelta(days=1)
            
        q_month = select(func.sum(Transaction.amount)).where(Transaction.date >= iter_date).where(Transaction.date <= m_end)
        q_month = apply_scope(q_month)
        m_total = session.exec(q_month).one() or 0.0
        
        trend.append({
            "month": iter_date.strftime("%b %Y"),
            "year": iter_date.year,
            "month_num": iter_date.month,
            "total": m_total
        })
        
        # Next month
        iter_date = m_end + timedelta(days=1)

    return {
        "currentMonthTotal": curr_total,
        "lastMonthTotal": prev_total,
        "categories": categories,
        "trend": trend
    }

@router.get("/trip/{trip_id}")
def get_trip_stats(trip_id: int, session: Session = Depends(get_session)):
    trip = session.get(Trip, trip_id)
    if not trip:
         raise HTTPException(status_code=404, detail="Trip not found")
         
    # 1. Total Trip Cost
    q_total = select(func.sum(Transaction.amount)).where(Transaction.trip_id == trip_id)
    total_spent = session.exec(q_total).one() or 0.0
    
    # 2. Category Breakdown
    q_cat = select(Transaction.category_id, Category.name, func.sum(Transaction.amount).label("total"))\
        .join(Category, isouter=True)\
        .where(Transaction.trip_id == trip_id)\
        .group_by(Transaction.category_id, Category.name)\
        .order_by(desc("total"))
        
    cat_results = session.exec(q_cat).all()
    categories = [{"id": r[0], "name": r[1] or "Uncategorized", "total": r[2]} for r in cat_results]
    
    return {
        "trip_name": trip.name,
        "total_spent": total_spent,
        "categories": categories
    }
