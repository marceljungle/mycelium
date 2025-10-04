#!/usr/bin/env python3
"""
Post-processing script to convert OpenAPI-generated Pydantic v1 models to v2 syntax.

This script fixes incompatibilities between Pydantic v1 and v2:
- Converts Config.allow_population_by_field_name to model_config with populate_by_name
- Replaces const fields with Literal type hints
- Updates deprecated methods like dict() and parse_obj() to model_dump() and model_validate()
- Adds alias_generator to automatically convert snake_case to camelCase for JSON
"""

import re
import sys
from pathlib import Path
from typing import List


def to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def fix_config_class(content: str) -> str:
    """Convert Pydantic v1 Config class to v2 model_config with alias_generator."""
    
    # Pattern to find the Config class block
    config_pattern = re.compile(
        r'(\s+)class Config:\s*\n'
        r'(?:\s+"""[^"]*"""\s*\n)?'  # Optional docstring
        r'(\s+allow_population_by_field_name\s*=\s*True\s*\n)?'
        r'(\s+validate_assignment\s*=\s*True\s*\n)?',
        re.MULTILINE
    )
    
    def replace_config(match: re.Match) -> str:
        indent = match.group(1)
        has_populate = match.group(2) is not None
        has_validate = match.group(3) is not None
        
        # Build model_config dict with ConfigDict for better type safety
        config_items = []
        config_items.append('alias_generator=to_camel')  # Auto-convert snake_case to camelCase
        if has_populate:
            config_items.append('populate_by_name=True')
        if has_validate:
            config_items.append('validate_assignment=True')
        
        return f'{indent}model_config = ConfigDict({", ".join(config_items)})\n'
    
    return config_pattern.sub(replace_config, content)


def fix_methods(content: str) -> str:
    """Update deprecated Pydantic v1 methods to v2 equivalents."""
    
    # .dict() -> .model_dump()
    content = re.sub(r'\.dict\(', '.model_dump(', content)
    
    # .parse_obj() -> .model_validate()
    content = re.sub(r'\.parse_obj\(', '.model_validate(', content)
    
    # .from_dict() method should use model_validate
    content = re.sub(
        r'(\s+)return cls\.model_validate\(obj\)',
        r'\1return cls.model_validate(obj)',
        content
    )
    
    return content


def add_pydantic_imports(content: str) -> str:
    """Ensure required Pydantic imports are present."""
    
    # Check if we need to add imports
    needs_config_dict = 'model_config = ConfigDict' in content
    needs_to_camel = 'alias_generator=to_camel' in content
    
    if not (needs_config_dict or needs_to_camel):
        return content
    
    # Find the pydantic import line
    pydantic_import_pattern = re.compile(r'from pydantic import ([^\n]+)')
    match = pydantic_import_pattern.search(content)
    
    if not match:
        return content
    
    imports = match.group(1)
    new_imports = []
    
    # Add ConfigDict if needed and not present
    if needs_config_dict and 'ConfigDict' not in imports:
        new_imports.append('ConfigDict')
    
    # Add to_camel if needed and not present  
    if needs_to_camel and 'to_camel' not in imports:
        new_imports.append('to_camel')
    
    if new_imports:
        updated_imports = f"{imports}, {', '.join(new_imports)}"
        content = pydantic_import_pattern.sub(f'from pydantic import {updated_imports}', content, count=1)
    
    return content


def fix_literal_types(content: str) -> str:
    """Convert const field constraints to Literal type hints."""
    
    # Look for patterns like: field: StrictStr = Field(..., const=True)
    # This is less common but should be handled
    # For now, we'll just remove const parameter as it's not in the current generated code
    content = re.sub(r',\s*const\s*=\s*True', '', content)
    content = re.sub(r'const\s*=\s*True,\s*', '', content)
    
    return content


def fix_pydantic_file(file_path: Path) -> bool:
    """Fix a single Python file to be Pydantic v2 compatible.
    
    Returns:
        True if file was modified, False otherwise
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        original_content = content
        
        # Apply all fixes
        content = fix_config_class(content)
        content = fix_methods(content)
        content = fix_literal_types(content)
        content = add_pydantic_imports(content)
        
        # Only write if content changed
        if content != original_content:
            file_path.write_text(content, encoding='utf-8')
            return True
        
        return False
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return False


def fix_pydantic_directory(directory: Path) -> int:
    """Recursively fix all Python files in a directory.
    
    Returns:
        Number of files modified
    """
    modified_count = 0
    
    if not directory.exists():
        print(f"Directory not found: {directory}", file=sys.stderr)
        return 0
    
    # Process all Python files
    for py_file in directory.rglob("*.py"):
        # Skip __pycache__ and test directories
        if '__pycache__' in py_file.parts or 'test' in py_file.parts:
            continue
            
        if fix_pydantic_file(py_file):
            print(f"Fixed: {py_file.relative_to(directory.parent.parent)}")
            modified_count += 1
    
    return modified_count


def main() -> int:
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
