#!/usr/bin/env python3
"""
Post-processing script to convert OpenAPI-generated Pydantic v1 models to v2 syntax.

This script fixes incompatibilities between Pydantic v1 and v2:
- Converts Config.allow_population_by_field_name to model_config with populate_by_name
- Replaces const fields with Literal type hints  
- Updates deprecated methods like dict() and parse_obj() to model_dump() and model_validate()
"""

import re
import sys
from pathlib import Path


def fix_config_class(content: str) -> str:
    """Convert Pydantic v1 Config class to v2 model_config."""
    
    config_pattern = re.compile(
        r'(\s+)class Config:\s*\n'
        r'(?:\s+"""[^"]*"""\s*\n)?'
        r'(\s+allow_population_by_field_name\s*=\s*True\s*\n)?'
        r'(\s+validate_assignment\s*=\s*True\s*\n)?',
        re.MULTILINE
    )
    
    def replace_config(match):
        indent = match.group(1)
        has_populate = match.group(2) is not None
        has_validate = match.group(3) is not None
        
        config_items = []
        if has_populate:
            config_items.append('"populate_by_name": True')
        if has_validate:
            config_items.append('"validate_assignment": True')
        
        if config_items:
            return f'{indent}model_config = {{{", ".join(config_items)}}}\n'
        return ''
    
    return config_pattern.sub(replace_config, content)


def fix_methods(content: str) -> str:
    """Update deprecated Pydantic v1 methods to v2 equivalents."""
    
    content = re.sub(r'\.dict\(', '.model_dump(', content)
    content = re.sub(r'\.parse_obj\(', '.model_validate(', content)
    
    return content


def add_pydantic_imports(content: str) -> str:
    """Ensure ConfigDict is imported if model_config is used."""
    
    if 'model_config = {' in content and 'from pydantic import' in content:
        if 'ConfigDict' not in content:
            content = re.sub(
                r'from pydantic import ([^\n]+)',
                r'from pydantic import \1, ConfigDict',
                content,
                count=1
            )
    
    return content


def fix_literal_types(content: str) -> str:
    """Convert const field constraints to Literal type hints."""
    
    content = re.sub(r',\s*const\s*=\s*True', '', content)
    content = re.sub(r'const\s*=\s*True,\s*', '', content)
    
    return content


def fix_pydantic_file(file_path):
    """Fix a single Python file to be Pydantic v2 compatible."""
    
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        content = fix_config_class(content)
        content = fix_methods(content)
        content = fix_literal_types(content)
        content = add_pydantic_imports(content)
        
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True
        
        return False
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False


def fix_pydantic_directory(directory):
    """Recursively fix all Python files in a directory."""
    
    modified_count = 0
    
    if not directory.exists():
        print(f"Directory not found: {directory}", file=sys.stderr)
        return 0
    
    for py_file in directory.rglob("*.py"):
        if '__pycache__' in py_file.parts or 'test' in py_file.parts:
            continue
            
        if fix_pydantic_file(py_file):
            print(f"Fixed: {py_file.relative_to(directory.parent.parent)}")
            modified_count += 1
    
    return modified_count


def main():
    """Main entry point for the script."""
    
    if len(sys.argv) < 2:
        print("Usage: fix_pydantic_v2.py <directory> [<directory2> ...]", file=sys.stderr)
        print("\nFixes OpenAPI-generated Pydantic v1 code to be v2 compatible", file=sys.stderr)
        return 1
    
    total_modified = 0
    
    for dir_path in sys.argv[1:]:
        directory = Path(dir_path)
        print(f"\nProcessing directory: {directory}")
        
        modified = fix_pydantic_directory(directory)
        total_modified += modified
        
        print(f"Modified {modified} files in {directory}")
    
    print(f"\n✓ Total files modified: {total_modified}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
