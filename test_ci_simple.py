import sys
import importlib
import os

# simple smoke test used by CI
# - ensure modules compile/import under different Python versions

# try importing core modules
try:
    import modules.exif_processor as exif
    import modules.main_application as main_app
except Exception as e:
    print('IMPORT_FAILED', e)
    raise

# basic sanity checks
assert hasattr(exif, 'find_exiftool_path')
assert hasattr(exif, 'get_safe_target_path')

print('SMOKE_OK')
