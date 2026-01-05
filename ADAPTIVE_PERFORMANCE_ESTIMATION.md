# Adaptive Performance Estimation Feature

## Overview

The adaptive performance estimation system provides accurate rename operation time estimates based on your system's actual performance and the complexity of your renaming pattern.

## How It Works

### 1. Automatic Background Benchmarking

When you load files (via "Select Files" or "Select Folder"), the application automatically starts a background benchmark:

- **Runs silently** while you configure your renaming pattern
- **Tests ~10 sample files** with various pattern complexities
- **Scenarios tested:**
  - Text only (0 EXIF fields)
  - 1 EXIF field + text
  - 2 EXIF fields + text
  - 3 EXIF fields + text
  - 4 EXIF fields + text
  - With/without EXIF metadata save

### 2. Pattern Complexity Analysis

The system analyzes your current pattern configuration:

- **EXIF fields:** Date, Camera, Lens, ISO, Aperture, Focal Length, Shutter Speed, etc.
- **Text fields:** Camera Prefix, Additional Text
- **Options:** "Save original filename to metadata" checkbox

### 3. Intelligent Time Estimation

Before every rename operation, you'll see an estimation dialog showing:

- **File count:** Number of files to be renamed
- **Pattern complexity:** E.g., "2 EXIF fields, 1 text field, metadata save enabled"
- **Estimated time range:** E.g., "7.0-12.0 seconds"
- **Confidence level:** 
  - "exact measurement" (100%) - matches benchmark scenario exactly
  - "similar scenario" (70%) - close to benchmarked pattern
  - "estimated" (50%) - interpolated from similar scenarios
  - "rough estimate" (30%) - no benchmark data yet

### 4. Adaptive Estimation

The estimation adapts to:

- ✅ Your system's performance (SSD vs HDD, CPU speed)
- ✅ File types in your batch (JPEG vs RAW)
- ✅ Pattern complexity (more EXIF fields = slower)
- ✅ EXIF save option (adds ~75-150ms per file)

## User Experience

### Workflow Example

1. **Load files** → Benchmark starts automatically in background
2. **Configure pattern** → Think about your naming scheme (~10-30 seconds)
3. **Click "Rename Files"** → See accurate time estimate
4. **Confirm or Cancel** → Proceed only if time is acceptable

### Dialog Example

```
⏱️ Operation Time Estimate

Ready to rename 250 files

Pattern complexity: 2 EXIF fields, 1 text field, metadata save enabled
Estimated time: 15.0-19.5 seconds
Confidence: similar scenario

Continue with rename operation?
[OK] [Cancel]
```

## Technical Details

### Benchmark Storage

- Benchmark results are stored in memory for the session
- Re-benchmarks automatically when loading new files
- No disk I/O for benchmark storage

### Performance Impact

- **Background benchmark:** 5-15 seconds (one-time per session)
- **Estimation calculation:** <10ms (instant)
- **No impact on rename speed** - estimation is pre-operation only

### Fallback Mode

If benchmark hasn't completed or failed:

- Uses conservative default estimates
- Shows "rough estimate (no benchmark)" confidence level
- Still provides useful guidance

## Benefits

### For Users

- ✅ **No surprises** - know how long operations will take
- ✅ **Informed decisions** - cancel large batches if time-sensitive
- ✅ **System-specific** - accurate for YOUR hardware
- ✅ **Pattern-aware** - adjusts for complex vs simple patterns

### For Workflow

- ✅ Better planning for large batches
- ✅ Understanding of pattern complexity impact
- ✅ Visibility into EXIF save performance cost
- ✅ Confidence in operation duration

## Configuration

### Benchmark Parameters

Located in `modules/performance_benchmark.py`:

```python
# Number of sample files to benchmark (default: 10)
max_samples = 10

# Threshold for showing estimation (always shows now)
# Previously was >50 files, now shows for all operations
```

### Disabling Feature

To disable the estimation dialog (not recommended):

1. Comment out the estimation dialog code in `main_application.py`
2. Look for "Operation Time Estimate" dialog
3. The background benchmark will still run (minimal overhead)

## Testing

Run the test suite:

```bash
python Tests/test_performance_benchmark.py
```

This will:
- Test pattern complexity analysis
- Run a full benchmark simulation
- Test estimation with and without benchmark data
- Verify all scenarios

## Future Enhancements

Potential improvements:

1. **Persistent benchmark cache** - Save results between sessions
2. **Machine learning** - Improve estimates over time based on actual operations
3. **Network drive detection** - Adjust estimates for network storage
4. **Historical tracking** - Show actual vs estimated time after operations
5. **Custom benchmarks** - Allow users to trigger re-benchmark manually

## Troubleshooting

### Benchmark Not Running

- Ensure you have at least 3 files loaded
- Check if ExifTool is available (enhances benchmark accuracy)
- Look in status bar for "Performance benchmark completed" message

### Inaccurate Estimates

- Wait for full benchmark to complete (shows in status bar)
- Ensure sample files are representative of your batch
- Check confidence level - low confidence means interpolated estimate

### Benchmark Takes Too Long

- Default is 10 samples - reduces to match file count if fewer
- Background execution - doesn't block UI
- Only runs once per file loading operation

## Implementation Files

- **`modules/performance_benchmark.py`** - Core benchmark engine
- **`modules/main_application.py`** - Estimation dialog integration  
- **`modules/ui/file_list_manager.py`** - Benchmark trigger on file load
- **`Tests/test_performance_benchmark.py`** - Test suite

---

**Note:** This feature was implemented to address the request for dynamic time estimation based on actual system performance and pattern complexity, replacing static estimates with adaptive, measured predictions.
