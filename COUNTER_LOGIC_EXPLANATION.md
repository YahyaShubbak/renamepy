# Counter Logic Improvement - Midnight Boundary Fix

## Problem Description

**Scenario:** User has photos taken around midnight (e.g., Abiball event)
- Photos taken at 23:50 on 2025-07-29
- Photos taken at 00:10 on 2025-07-30  
- User wants to use **same prefix** (e.g., "Abiball") but **exclude date** from filename

**Previous Behavior (Problematic):**
```
Abiball-001.ARW  (23:50, 2025-07-29)
Abiball-002.ARW  (23:55, 2025-07-29)
Abiball-001.ARW  (00:05, 2025-07-30) ❌ CONFLICT!
Abiball-002.ARW  (00:10, 2025-07-30) ❌ CONFLICT!
```

Result: `Abiball-001_conflict_001.ARW`, `Abiball-002_conflict_001.ARW`

## New Behavior (Fixed)

### When `use_date = True` (Include date in filename)
Counter resets per date - **no change in behavior**
```
2025-07-29-Abiball-001.ARW  (23:50)
2025-07-29-Abiball-002.ARW  (23:55)
2025-07-30-Abiball-001.ARW  (00:05) ✅ NO CONFLICT
2025-07-30-Abiball-002.ARW  (00:10) ✅ NO CONFLICT  
```

### When `use_date = False` (Exclude date from filename) 
Counter continues across dates - **NEW BEHAVIOR**
```
Abiball-001.ARW  (23:50, 2025-07-29)
Abiball-002.ARW  (23:55, 2025-07-29)  
Abiball-003.ARW  (00:05, 2025-07-30) ✅ NO CONFLICT
Abiball-004.ARW  (00:10, 2025-07-30) ✅ NO CONFLICT
```

## Implementation Details

1. **Chronological Sorting**: When `use_date=False`, files are sorted by timestamp before numbering
2. **Intelligent Counter**: 
   - `use_date=True`: `date_counter[date_taken]` (per-date counter)
   - `use_date=False`: `date_counter["all_files"]` (global counter)
3. **Timestamp Priority**: EXIF date > File modification time

## Code Changes

- `optimized_rename_files()` in `RenameWorkerThread` 
- `rename_files()` standalone function
- Added chronological sorting for consistent numbering
- Updated counter logic with conditional behavior

## Test Case

Using the example files from the image:
- `_DSC0590.ARW` / `_DSC0590.JPG` (evening)
- `_DSC0591.ARW` / `_DSC0591.JPG` (evening) 
- `_DSC0593.ARW` / `_DSC0593.JPG` (after midnight)
- `_DSC0594.ARW` / `_DSC0594.JPG` (after midnight)
- `_DSC0595.ARW` / `_DSC0595.JPG` (after midnight)

**With `use_date=False` and prefix "Abiball":**
```
Abiball-001.ARW  (_DSC0590.ARW)
Abiball-001.JPG  (_DSC0590.JPG) 
Abiball-002.ARW  (_DSC0591.ARW)
Abiball-002.JPG  (_DSC0591.JPG)
Abiball-003.ARW  (_DSC0593.ARW)  # Different date but continuous counter
Abiball-003.JPG  (_DSC0593.JPG)
Abiball-004.ARW  (_DSC0594.ARW)
Abiball-004.JPG  (_DSC0594.JPG)
Abiball-005.ARW  (_DSC0595.ARW)
Abiball-005.JPG  (_DSC0595.JPG)
```

## Benefits

1. **No More Conflicts**: Eliminates midnight boundary conflicts when date is excluded
2. **Logical Numbering**: Continuous sequence makes sense for single-event shooting
3. **Backward Compatible**: Existing behavior unchanged when date is included
4. **Chronological Order**: Files numbered in actual shooting order
