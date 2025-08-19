# Job Card Integration System

## Overview

The Job Card Integration system enables seamless workflow transitions between in-house and outsourced manufacturing processes. It provides complete traceability from production orders through job cards to job work completion.

## Key Features

### 1. Database Integration
- **job_work_id** foreign key in job_cards table links job cards to job work
- **source_job_card_id** in job_works table tracks which job card created the job work
- **production_id** in job_works table connects job work to production orders

### 2. Workflow Management
- Dynamic switching between in-house and outsourced processing
- Automatic job work creation when outsourcing job cards
- Complete material flow tracking and batch integration
- Real-time status updates across all manufacturing processes

### 3. Integration Dashboard
- Located at `/job-card-integration/dashboard`
- Real-time status overview with progress tracking
- Integration metrics showing linked job work relationships
- Quick action buttons for seamless workflow navigation
- Detailed job card table with outsourcing capabilities

## How to Use

### Accessing the Dashboard
1. Log into the application
2. Navigate to "Job Card Integration" in the sidebar (marked with NEW badge)
3. View comprehensive status overview and workflow management tools

### Outsourcing Process
1. From the integration dashboard, identify in-house job cards
2. Click the outsource button for eligible job cards
3. Select vendor, set expected return date, and add notes
4. System automatically creates linked job work and updates job card status

### Status Tracking
- **In-House**: Job cards being processed internally
- **Outsourced**: Job cards sent to external vendors
- **Linked**: Job cards connected to job work orders
- **Pending Receipts**: Outsourced work awaiting GRN receipt

## Technical Implementation

### Service Layer
- `JobCardJobWorkIntegration` service handles all workflow operations
- Methods for outsourcing, receiving work, and status tracking
- Automatic material batch tracking and movement records

### Database Schema
```sql
-- Added to job_cards table
job_work_id INTEGER REFERENCES job_works(id)
auto_created_job_work BOOLEAN DEFAULT FALSE

-- Added to job_works table  
production_id INTEGER REFERENCES productions(id)
source_job_card_id INTEGER REFERENCES job_cards(id)
```

### Routes
- `GET /job-card-integration/dashboard` - Main integration dashboard
- `POST /job-card-integration/outsource/{job_card_id}` - Outsource job card
- `GET /job-card-integration/api/job-card/{id}/outsourcing-options` - API for vendor options

## Benefits

1. **Flexible Manufacturing**: Switch between in-house and outsourced as needed
2. **Complete Traceability**: Track materials from raw to finished through all processes
3. **Real-time Visibility**: Live status updates across the entire workflow
4. **Vendor Management**: Comprehensive outsourcing with rate tracking and lead times
5. **Batch Integration**: Automatic batch allocation and movement tracking

## Sample Data

The system includes sample job cards demonstrating:
- JC-001: In-house cutting operation (planned)
- JC-002: In-house bending operation (60% complete)  
- JC-003: Outsourced zinc coating (linked to JW-000001)

## Future Enhancements

- Vendor rate management integration
- Automatic cost calculations based on actual rates
- Advanced scheduling and capacity planning
- Mobile app support for real-time updates
- Integration with external vendor systems