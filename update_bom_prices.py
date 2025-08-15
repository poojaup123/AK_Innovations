#!/usr/bin/env python3
"""
BOM Price Update Utility

This script updates all item prices based on their BOM calculations.
Run this when:
- New BOMs are created
- Material costs change
- Labor/overhead rates are modified
- To sync all BOM-calculated prices

Usage:
    python update_bom_prices.py
"""

import sys
import os

# Add the current directory to the Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import BOM

def update_all_bom_prices():
    """Update all item prices based on BOM calculations"""
    with app.app_context():
        print("🔄 Starting BOM price update process...")
        print("=" * 50)
        
        try:
            # Update all BOM calculations first
            updated_bom_count = BOM.update_all_bom_calculations()
            if updated_bom_count > 0:
                print(f"✅ Updated {updated_bom_count} BOMs with consistent output quantities")
            
            # Update all item prices based on BOM calculations
            updated_items = BOM.update_all_item_prices_from_bom()
            
            if updated_items:
                print(f"\n🎯 Successfully updated prices for {len(updated_items)} items:")
                print("-" * 80)
                print(f"{'Item Code':<12} {'Item Name':<25} {'Old Price':<10} {'New Price':<10} {'Material':<10} {'Labor':<8}")
                print("-" * 80)
                
                for item in updated_items:
                    print(f"{item['item_code']:<12} {item['item_name'][:24]:<25} "
                          f"₹{item['old_price']:<9.2f} ₹{item['new_price']:<9.2f} "
                          f"₹{item['material_cost']:<9.2f} ₹{item['labor_cost']:<7.2f}")
                
                print("-" * 80)
                total_value_change = sum(item['new_price'] - item['old_price'] for item in updated_items)
                print(f"💰 Total value change: ₹{total_value_change:,.2f}")
                
            else:
                print("✅ All item prices are already up to date with their BOM calculations.")
                
            print("\n🎉 BOM price update completed successfully!")
            
        except Exception as e:
            print(f"❌ Error updating BOM prices: {e}")
            return False
        
        return True

if __name__ == "__main__":
    print("Factory Management System - BOM Price Update Utility")
    print("This utility will update all item prices based on BOM calculations.")
    
    # Confirm before running
    confirm = input("\nDo you want to proceed? (y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        success = update_all_bom_prices()
        exit_code = 0 if success else 1
        sys.exit(exit_code)
    else:
        print("Operation cancelled.")
        sys.exit(0)