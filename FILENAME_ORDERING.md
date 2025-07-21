# Filename Ordering Customization

## Overview
The RenameFiles application now supports intuitive filename component ordering with the sequential number always positioned at the end of the filename.

## Problem Solved
Previously, filenames looked like: `2025-07-18-78-Sarah30.ARW`  
Now they correctly appear as: `2025-07-18-Sarah30-78.ARW`

The sequential number (78) is now always at the end, making files easier to sort and read.

## Features

### 1. Predefined Ordering Options
Choose from several common filename patterns:

1. **Date-Prefix-Additional-Camera-Lens-Number (Default)**
   - Format: `2025-07-21-A7R3-Sarah30-ILCE-7RM3-FE24-70F28GM-78.ARW`
   - Best for: General photography workflow

2. **Prefix-Additional-Date-Camera-Lens-Number**
   - Format: `A7R3-Sarah30-2025-07-21-ILCE-7RM3-FE24-70F28GM-78.ARW`
   - Best for: Camera-centric organization

3. **Date-Camera-Lens-Prefix-Additional-Number**
   - Format: `2025-07-21-ILCE-7RM3-FE24-70F28GM-A7R3-Sarah30-78.ARW`
   - Best for: Technical/gear-focused workflows

4. **Additional-Prefix-Date-Camera-Lens-Number**
   - Format: `Sarah30-A7R3-2025-07-21-ILCE-7RM3-FE24-70F28GM-78.ARW`
   - Best for: Event/subject-focused organization

### 2. Custom Order Dialog
- Drag and drop components to create your own order
- Sequential number is always automatically added at the end
- Reset to default option available
- Real-time preview updates

### 3. Component Definitions
- **Date**: Year-Month-Day (e.g., 2025-07-21)
- **Prefix**: User-defined camera prefix (e.g., A7R3)
- **Additional**: User-defined additional info (e.g., Sarah30)
- **Camera**: EXIF camera model (e.g., ILCE-7RM3)
- **Lens**: EXIF lens model (e.g., FE24-70F28GM)
- **Number**: Sequential counter (always at end, e.g., 78)

## Usage

1. **Select Predefined Order**:
   - Use the "Filename Order" dropdown
   - Choose from the available patterns
   - Preview updates automatically

2. **Create Custom Order**:
   - Select "Custom Order..." from dropdown
   - Drag components in the dialog to reorder
   - Click "OK" to apply
   - Use "Reset to Default" to restore original order

3. **Preview Your Changes**:
   - The preview box shows exactly how files will be named
   - Updates in real-time as you change settings
   - Includes the sequential number at the end

## Benefits

### Improved Sorting
- Sequential numbers at the end ensure proper chronological sorting
- Files from the same shoot stay grouped together
- Natural alphabetical order matches capture sequence

### Better Readability
- Important information (date, event) comes first
- Technical details (camera, lens) are clearly separated
- Sequential number provides clear shot identification

### Flexible Organization
- Different workflows can use different patterns
- Custom orders support unique requirements
- Maintains compatibility with existing files

## Technical Implementation

### Core Function
```python
def get_filename_components_static(date_taken, camera_prefix, additional, 
                                 camera_model, lens_model, use_camera, 
                                 use_lens, num, custom_order):
    # Builds ordered filename components
    # Sequential number always added at end
```

### Key Features
- **Component Validation**: Empty components are automatically excluded
- **Sequential Number Guarantee**: Always appears at the end regardless of order
- **Real-time Preview**: Updates immediately when order changes
- **Thread-Safe**: Works with background processing

### Example Transformations
```
Old format: 2025-07-18-78-Sarah30.ARW
New format: 2025-07-18-Sarah30-78.ARW

Components: [Date] [Sequential] [Additional] → [Date] [Additional] [Sequential]
```

## Compatibility

- **Backward Compatible**: Existing functionality unchanged
- **Default Behavior**: Uses traditional date-first ordering
- **Migration Safe**: No impact on already renamed files
- **Performance**: No performance impact, cached processing maintained

## Testing

Run the test script to verify functionality:
```bash
python test_filename_ordering.py
```

Tests cover:
- All predefined ordering patterns
- Edge cases with missing components
- Special character handling
- Sequential number positioning
- Component validation

## Future Enhancements

Potential future improvements:
- Save/load custom ordering presets
- Per-folder ordering preferences
- Advanced component formatting options
- Template-based naming system
