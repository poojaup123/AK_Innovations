# Phase 2 Consolidation Plan - Factory Management System

## Current Structure Analysis
- **7 utility files** scattered at root level
- **15 service files** in services/ directory (well organized)
- **17 model files** scattered at root level  
- **11 form files** scattered at root level

## Phase 2A: Utility Files Consolidation (SAFE - Low Risk)

### Step 1: Create utils/ directory and consolidate
```
CREATE: utils/
MOVE: utils.py → utils/__init__.py (main utilities)
MOVE: utils_batch_tracking.py → utils/batch_tracking.py
MOVE: utils_documents.py → utils/documents.py
MOVE: utils_export.py → utils/export.py
MOVE: utils_ocr.py → utils/ocr.py

MOVE: services_batch_management.py → services/batch_management.py
MOVE: services_unified_inventory.py → services/unified_inventory.py
```

## Phase 2B: Models Organization (MEDIUM Risk - Requires Import Updates)

### Step 2: Create models/ directory and consolidate by domain
```
CREATE: models/
MOVE: models.py → models/__init__.py (core models)
MOVE: models_accounting*.py → models/accounting.py (consolidated)
MOVE: models_batch*.py → models/batch.py (consolidated)
MOVE: models_grn*.py → models/grn.py (consolidated)
MOVE: models_settings.py → models/settings.py
MOVE: models_department.py → models/department.py
MOVE: models_document.py → models/document.py
MOVE: models_uom.py → models/uom.py
etc.
```

## Phase 2C: Forms Organization (MEDIUM Risk - Requires Import Updates)

### Step 3: Create forms/ directory and consolidate by domain
```
CREATE: forms/
MOVE: forms.py → forms/__init__.py (core forms)
MOVE: forms_accounting*.py → forms/accounting.py (consolidated)
MOVE: forms_grn*.py → forms/grn.py (consolidated)
MOVE: forms_jobwork*.py → forms/jobwork.py (consolidated)
etc.
```

## Benefits After Phase 2
- **Professional directory structure**
- **Logical organization by domain**
- **Easier to find related files**
- **Reduced root directory clutter**
- **Improved maintainability**

## Risk Mitigation
- **Start with utilities** (lowest risk)
- **Update imports systematically**
- **Test after each consolidation**
- **Keep backups of changes**