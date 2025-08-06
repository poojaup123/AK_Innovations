# Multi-State Inventory Tracking System - Complete Workflow

## Overview
The Multi-State Inventory Tracking system transforms traditional single-stock inventory into a comprehensive manufacturing workflow that tracks materials through four distinct states: Raw Material, Work in Progress (WIP), Finished Goods, and Scrap.

## The Four States Explained

### 1. Raw Material (qty_raw)
- **Purpose**: Initial stock ready for processing
- **Example**: 50 pieces of steel plates in warehouse
- **Color Code**: Blue (Primary)
- **When Used**: Materials just received from suppliers, ready to be sent for processing

### 2. Work in Progress - WIP (qty_wip)
- **Purpose**: Materials currently being processed (sent for job work)
- **Example**: 50 pieces sent to vendor for cutting/machining
- **Color Code**: Orange (Warning)
- **When Used**: Materials are out of your facility being processed by vendors or internal departments

### 3. Finished Goods (qty_finished)
- **Purpose**: Completed materials received back from processing
- **Example**: 48 pieces successfully processed and returned
- **Color Code**: Green (Success)
- **When Used**: Materials completed processing and ready for final use/sale

### 4. Scrap (qty_scrap)
- **Purpose**: Rejected or damaged materials during processing
- **Example**: 2 pieces damaged during processing
- **Color Code**: Red (Danger)
- **When Used**: Materials that failed quality checks or were damaged

## Complete Workflow Example

### Initial State
```
Steel Plate Item:
├── Raw Material: 100 pieces
├── WIP: 0 pieces
├── Finished: 0 pieces
├── Scrap: 0 pieces
└── Total Stock: 100 pieces
```

### Step 1: Create Job Work (Send Materials for Processing)
When you create a job work to send 50 pieces for cutting:

**System Action**: Automatically moves materials Raw → WIP
```
Steel Plate Item:
├── Raw Material: 50 pieces (-50)
├── WIP: 50 pieces (+50)
├── Finished: 0 pieces
├── Scrap: 0 pieces
└── Total Stock: 100 pieces (unchanged)
```

**What Happens**:
- System calls `item.move_to_wip(50)`
- Deducts 50 from qty_raw
- Adds 50 to qty_wip
- Logs movement in job work notes

### Step 2: Material Inspection (Receive Processed Materials)
When vendor returns materials and you inspect them:
- Received: 50 pieces
- Passed Quality Check: 48 pieces
- Failed/Damaged: 2 pieces

**System Action**: Automatically moves materials WIP → Finished + Scrap
```
Steel Plate Item:
├── Raw Material: 50 pieces
├── WIP: 0 pieces (-50)
├── Finished: 48 pieces (+48)
├── Scrap: 2 pieces (+2)
└── Total Stock: 100 pieces (unchanged)
```

**What Happens**:
- System calls `item.receive_from_wip(48, 2)`
- Deducts 50 from qty_wip
- Adds 48 to qty_finished
- Adds 2 to qty_scrap
- Updates current_stock = qty_raw + qty_finished = 98 pieces available

## Key Benefits

### 1. Complete Manufacturing Visibility
- Track exactly where materials are in your production process
- Know how much is being processed vs. ready for use
- Monitor scrap rates and quality issues

### 2. Accurate Stock Calculations
- **Total Stock**: Sum of all states (Raw + WIP + Finished + Scrap)
- **Available Stock**: Raw + Finished (excludes WIP since it's not in your facility)
- **Legacy Compatibility**: current_stock = available_stock for existing reports

### 3. Automatic State Management
- No manual tracking required
- System automatically handles transitions
- Prevents inventory inconsistencies
- Maintains audit trail of all movements

### 4. Real-time Workflow Monitoring
- See materials currently being processed (WIP)
- Track completion rates and scrap percentages
- Monitor vendor performance and delivery times

## Business Intelligence

### Production Planning
```
Before Sending Job Work:
✓ Check qty_raw for available materials
✓ Verify sufficient stock for production orders
✓ Plan based on available vs. total stock

During Processing:
✓ Monitor qty_wip to track outstanding work
✓ Follow up with vendors on delivery schedules
✓ Plan next batch based on expected returns

After Completion:
✓ Analyze scrap rates (qty_scrap / total_processed)
✓ Update planning based on actual yields
✓ Adjust minimum stock levels accordingly
```

### Quality Management
- Track scrap percentage by vendor
- Identify problematic processes
- Monitor quality trends over time
- Set alerts for high scrap rates

### Financial Accuracy
- Inventory valuation includes all states
- Work-in-progress tracking for financial reporting
- Scrap loss accounting
- Accurate cost of goods sold calculations

## Technical Implementation

### Database Structure
```sql
items table:
├── qty_raw (Float) - Raw material stock
├── qty_wip (Float) - Work in progress stock
├── qty_finished (Float) - Finished goods stock
├── qty_scrap (Float) - Scrap/rejected stock
└── current_stock (Float) - Legacy field (qty_raw + qty_finished)
```

### Smart Methods
```python
# Move materials to WIP when creating job work
item.move_to_wip(quantity)

# Receive materials from WIP when inspection complete
item.receive_from_wip(finished_qty, scrap_qty)

# Calculate totals
item.total_stock  # Sum of all states
item.available_stock  # Raw + Finished only
```

### Integration Points
- **Job Work Creation**: Automatically deducts from Raw, adds to WIP
- **Material Inspection**: Automatically deducts from WIP, adds to Finished/Scrap
- **Purchase Orders**: Add to Raw when materials received
- **Sales Orders**: Deduct from Available (Raw + Finished)

## Dashboard Features

### Multi-State View
- Color-coded columns for each state
- Visual indicators (icons) for active states
- Real-time totals and percentages
- Low stock alerts considering available stock

### Workflow Guidance
- Clear explanation of each state
- Process flow indicators
- Status badges and progress tracking
- Audit trail of state changes

This system provides complete visibility into your manufacturing workflow while maintaining compatibility with existing processes and reports.