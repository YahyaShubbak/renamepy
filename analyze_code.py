#!/usr/bin/env python3
"""
Code Quality Analysis - Find optimization opportunities
"""

import os
import re
from collections import Counter

MODULES_DIR = "modules"

def analyze_imports(file_path):
    """Analyze imports in a Python file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all import statements
    import_pattern = r'^(?:from\s+[\w.]+\s+)?import\s+.+$'
    imports = re.findall(import_pattern, content, re.MULTILINE)
    
    # Find imports inside functions
    function_imports = []
    in_function = False
    for line in content.split('\n'):
        if re.match(r'^def\s+\w+|^class\s+\w+', line):
            in_function = True
        elif in_function and (line and not line[0].isspace()):
            in_function = False
        
        if in_function and ('import ' in line):
            function_imports.append(line.strip())
    
    return imports, function_imports

def count_lines_of_code(file_path):
    """Count actual lines of code (excluding comments and blanks)"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    total = len(lines)
    blank = sum(1 for line in lines if not line.strip())
    comments = sum(1 for line in lines if line.strip().startswith('#'))
    docstrings = 0
    
    in_docstring = False
    for line in lines:
        if '"""' in line or "'''" in line:
            in_docstring = not in_docstring
            if in_docstring:
                docstrings += 1
        elif in_docstring:
            docstrings += 1
    
    code = total - blank - comments - docstrings
    return total, code, blank, comments, docstrings

def find_duplicate_code(file_path):
    """Find potential duplicate code blocks"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Look for similar function definitions
    functions = []
    for i, line in enumerate(lines):
        if re.match(r'^\s*def\s+(\w+)', line):
            match = re.match(r'^\s*def\s+(\w+)', line)
            functions.append((match.group(1), i+1))
    
    return functions

def analyze_complexity(file_path):
    """Estimate code complexity"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count control structures
    if_count = len(re.findall(r'\bif\b', content))
    for_count = len(re.findall(r'\bfor\b', content))
    while_count = len(re.findall(r'\bwhile\b', content))
    try_count = len(re.findall(r'\btry\b', content))
    
    return {
        'if': if_count,
        'for': for_count,
        'while': while_count,
        'try': try_count,
        'total': if_count + for_count + while_count + try_count
    }

print("="*70)
print("🔍 Code Quality Analysis")
print("="*70)

# Analyze all Python files in modules
files = [f for f in os.listdir(MODULES_DIR) if f.endswith('.py') and f != '__init__.py']

total_stats = {
    'total_lines': 0,
    'code_lines': 0,
    'files': 0
}

print("\n📊 File Analysis:")
print("-"*70)

results = []
for filename in sorted(files):
    file_path = os.path.join(MODULES_DIR, filename)
    
    # Skip empty files
    if os.path.getsize(file_path) == 0:
        continue
    
    total, code, blank, comments, docstrings = count_lines_of_code(file_path)
    imports, func_imports = analyze_imports(file_path)
    complexity = analyze_complexity(file_path)
    functions = find_duplicate_code(file_path)
    
    total_stats['total_lines'] += total
    total_stats['code_lines'] += code
    total_stats['files'] += 1
    
    results.append({
        'file': filename,
        'total': total,
        'code': code,
        'imports': len(imports),
        'func_imports': len(func_imports),
        'functions': len(functions),
        'complexity': complexity['total']
    })

# Sort by code lines
results.sort(key=lambda x: x['code'], reverse=True)

for r in results:
    print(f"\n{r['file']}:")
    print(f"  Lines: {r['total']:,} total, {r['code']:,} code")
    print(f"  Imports: {r['imports']} (top-level), {r['func_imports']} (in functions)")
    print(f"  Functions: {r['functions']}")
    print(f"  Complexity: {r['complexity']} control structures")
    
    if r['code'] > 500:
        print(f"  ⚠️  LARGE FILE - Consider splitting!")
    if r['func_imports'] > 5:
        print(f"  ⚠️  Many function-level imports - move to top")

print("\n" + "="*70)
print("📈 Summary:")
print("="*70)
print(f"Total files: {total_stats['files']}")
print(f"Total lines: {total_stats['total_lines']:,}")
print(f"Code lines: {total_stats['code_lines']:,}")
print(f"Avg lines/file: {total_stats['total_lines']//total_stats['files']:,}")

# Find top issues
print("\n🎯 Optimization Opportunities:")
print("-"*70)

large_files = [r for r in results if r['code'] > 500]
if large_files:
    print(f"\n1️⃣ Large files to refactor ({len(large_files)}):")
    for r in large_files:
        print(f"   - {r['file']}: {r['code']:,} lines")

complex_files = [r for r in results if r['complexity'] > 100]
if complex_files:
    print(f"\n2️⃣ Complex files to simplify ({len(complex_files)}):")
    for r in complex_files:
        print(f"   - {r['file']}: {r['complexity']} control structures")

import_heavy = [r for r in results if r['func_imports'] > 3]
if import_heavy:
    print(f"\n3️⃣ Files with many function-level imports ({len(import_heavy)}):")
    for r in import_heavy:
        print(f"   - {r['file']}: {r['func_imports']} function imports")

print("\n" + "="*70)
