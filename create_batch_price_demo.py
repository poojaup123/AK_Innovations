"""
Create demo batch price history data
"""

from app import app, db
from models import Item
from models.batch import InventoryBatch, BatchPriceHistory
from datetime import datetime, date, timedelta
import random

def create_batch_price_demo():
    """Create demo batch price history for existing batches"""
    
    with app.app_context():
        try:
            # Get some existing batches
            batches = InventoryBatch.query.limit(10).all()
            
            if not batches:
                print("No batches found. Please create some inventory batches first.")
                return
            
            # Price scenarios for demo
            scenarios = [
                {
                    'price_type': 'purchase',
                    'source': 'grn_creation',
                    'notes': 'Initial purchase price from GRN receipt'
                },
                {
                    'price_type': 'standard',
                    'source': 'standard_cost_update',
                    'notes': 'Standard cost set for accounting valuation'
                },
                {
                    'price_type': 'actual',
                    'source': 'freight_addition',
                    'notes': 'Actual cost including freight and handling charges'
                },
                {
                    'price_type': 'purchase',
                    'source': 'manual_update',
                    'notes': 'Price increased due to raw material cost inflation'
                },
                {
                    'price_type': 'market',
                    'source': 'market_adjustment',
                    'notes': 'Market price adjustment based on current demand'
                }
            ]
            
            created_records = 0
            
            for batch in batches:
                print(f"Creating price history for batch: {batch.batch_code}")
                
                # Create 3-5 price records per batch
                num_records = random.randint(3, 5)
                base_price = batch.purchase_rate or random.uniform(100, 500)
                current_price = base_price
                
                for i in range(num_records):
                    scenario = random.choice(scenarios)
                    
                    # Create price variation
                    if i == 0:
                        # First record - initial price
                        new_price = base_price
                        effective_date = date.today() - timedelta(days=random.randint(30, 90))
                    else:
                        # Subsequent records - price changes
                        price_change = random.uniform(-0.2, 0.3)  # -20% to +30% change
                        new_price = current_price * (1 + price_change)
                        effective_date = date.today() - timedelta(days=random.randint(1, 30))
                    
                    # Check if price history already exists
                    existing = BatchPriceHistory.query.filter_by(
                        batch_id=batch.id,
                        price_type=scenario['price_type'],
                        effective_date=effective_date
                    ).first()
                    
                    if not existing:
                        price_history = BatchPriceHistory(
                            batch_id=batch.id,
                            item_id=batch.item_id,
                            price_type=scenario['price_type'],
                            new_price=round(new_price, 2),
                            effective_date=effective_date,
                            source=scenario['source'],
                            source_ref_number=f"DEMO-{batch.batch_code}-{i+1}",
                            notes=scenario['notes'],
                            currency='INR'
                        )
                        
                        # Calculate change from previous record
                        prev_record = BatchPriceHistory.query.filter_by(
                            batch_id=batch.id,
                            price_type=scenario['price_type']
                        ).filter(
                            BatchPriceHistory.effective_date < effective_date
                        ).order_by(BatchPriceHistory.effective_date.desc()).first()
                        
                        if prev_record:
                            price_history.previous_price = prev_record.new_price
                            price_history.price_change_amount = new_price - prev_record.new_price
                            price_history.price_change_percent = (
                                (new_price - prev_record.new_price) / prev_record.new_price * 100
                            ) if prev_record.new_price > 0 else 0
                        
                        db.session.add(price_history)
                        created_records += 1
                        current_price = new_price
                
                # Update batch with latest purchase rate
                latest_purchase = BatchPriceHistory.query.filter_by(
                    batch_id=batch.id,
                    price_type='purchase'
                ).order_by(BatchPriceHistory.effective_date.desc()).first()
                
                if latest_purchase:
                    batch.purchase_rate = latest_purchase.new_price
            
            db.session.commit()
            print(f"\n✅ Successfully created {created_records} batch price history records!")
            
            # Show summary
            total_batches = InventoryBatch.query.count()
            total_price_records = BatchPriceHistory.query.count()
            
            print(f"\n📊 Summary:")
            print(f"   • Total batches: {total_batches}")
            print(f"   • Total price history records: {total_price_records}")
            print(f"   • Average price records per batch: {total_price_records/total_batches:.1f}")
            
            # Show recent price changes
            recent_changes = BatchPriceHistory.query.order_by(
                BatchPriceHistory.effective_date.desc()
            ).limit(5).all()
            
            print(f"\n🔄 Recent Price Changes:")
            for record in recent_changes:
                change_text = f"+₹{record.price_change_amount:.2f}" if record.price_change_amount and record.price_change_amount > 0 else f"₹{record.price_change_amount:.2f}" if record.price_change_amount else "New"
                print(f"   • {record.batch.batch_code} ({record.price_type}): ₹{record.new_price:.2f} ({change_text})")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating demo data: {str(e)}")

if __name__ == '__main__':
    create_batch_price_demo()