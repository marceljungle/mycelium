#!/usr/bin/env python3
"""
Validation script to check if the Mycelium frontend static files are properly configured.
This script helps verify that the static file serving fix is working correctly.
"""

from pathlib import Path
import sys

def check_frontend_files():
    """Check if frontend files are properly built and organized."""
    print("🔍 Checking frontend static files...")
    
    # Check if frontend_dist exists
    frontend_dist = Path("src/mycelium/frontend_dist")
    if not frontend_dist.exists():
        print("❌ Frontend dist directory not found!")
        print("   Run: ./build_frontend.sh")
        return False
    
    print("✅ Frontend dist directory exists")
    
    # Check key files
    index_html = frontend_dist / "index.html"
    if not index_html.exists():
        print("❌ index.html not found!")
        return False
    print("✅ index.html exists")
    
    # Check _next directory
    next_dir = frontend_dist / "_next"
    if not next_dir.exists():
        print("❌ _next directory not found!")
        return False
    print("✅ _next directory exists")
    
    # Check CSS files
    css_dir = next_dir / "static" / "css"
    if not css_dir.exists():
        print("❌ CSS directory not found!")
        return False
    
    css_files = list(css_dir.glob("*.css"))
    if not css_files:
        print("❌ No CSS files found!")
        return False
    print(f"✅ Found {len(css_files)} CSS file(s)")
    
    # Check JS files
    js_dir = next_dir / "static" / "chunks"
    if not js_dir.exists():
        print("❌ JS chunks directory not found!")
        return False
    
    js_files = list(js_dir.glob("*.js"))
    if not js_files:
        print("❌ No JS files found!")
        return False
    print(f"✅ Found {len(js_files)} JavaScript file(s)")
    
    return True

def check_html_content():
    """Check if HTML contains the expected asset paths."""
    print("\n🔍 Checking HTML content...")
    
    index_html = Path("src/mycelium/frontend_dist/index.html")
    if not index_html.exists():
        print("❌ index.html not found!")
        return False
    
    content = index_html.read_text()
    
    # Check for CSS links
    if '/_next/static/css/' not in content:
        print("❌ CSS links not found in HTML!")
        return False
    print("✅ CSS links found in HTML")
    
    # Check for JS scripts
    if '/_next/static/chunks/' not in content:
        print("❌ JS script tags not found in HTML!")
        return False
    print("✅ JS script tags found in HTML")
    
    return True

def check_package_config():
    """Check if package configuration includes frontend files."""
    print("\n🔍 Checking package configuration...")
    
    pyproject_toml = Path("pyproject.toml")
    if not pyproject_toml.exists():
        print("❌ pyproject.toml not found!")
        return False
    
    content = pyproject_toml.read_text()
    
    if 'frontend_dist/**' not in content:
        print("❌ frontend_dist not included in package data!")
        return False
    print("✅ frontend_dist included in package configuration")
    
    return True

def main():
    """Run all validation checks."""
    print("🍄 Mycelium Frontend Validation")
    print("=" * 40)
    
    checks = [
        check_frontend_files,
        check_html_content,
        check_package_config
    ]
    
    all_passed = True
    for check in checks:
        if not check():
            all_passed = False
    
    print("\n" + "=" * 40)
    if all_passed:
        print("🎉 All checks passed! Frontend should work correctly.")
        print("\nNext steps:")
        print("1. Build the wheel: pip wheel .")
        print("2. Install: pip install mycelium-*.whl")
        print("3. Run: mycelium server")
        print("4. Visit: http://localhost:8000")
    else:
        print("❌ Some checks failed! Please fix the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()