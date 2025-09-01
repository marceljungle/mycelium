#!/usr/bin/env python3
"""
Validation script to verify frontend routing fixes are working correctly.
"""

import os
import subprocess
import sys
from pathlib import Path


def check_file_exists(file_path: Path, description: str) -> bool:
    """Check if a file exists and report result."""
    if file_path.exists():
        print(f"✓ {description}: {file_path}")
        return True
    else:
        print(f"✗ {description}: {file_path} (NOT FOUND)")
        return False


def check_content_in_file(file_path: Path, content: str, description: str) -> bool:
    """Check if content exists in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
            if content in file_content:
                print(f"✓ {description}: Found '{content}' in {file_path.name}")
                return True
            else:
                print(f"✗ {description}: '{content}' not found in {file_path.name}")
                return False
    except Exception as e:
        print(f"✗ {description}: Error reading {file_path} - {e}")
        return False


def main():
    """Validate frontend routing fixes."""
    print("🍄 Mycelium Frontend Routing Validation")
    print("=" * 50)
    
    issues = []
    
    # Check main frontend build exists
    main_frontend_path = Path("src/mycelium/frontend_dist")
    main_index = main_frontend_path / "index.html"
    
    if not check_file_exists(main_index, "Main frontend index.html"):
        issues.append("Main frontend not built")
    else:
        # Check main frontend contains normal Mycelium interface
        if not check_content_in_file(main_index, "🍄 Mycelium", "Main frontend title"):
            issues.append("Main frontend doesn't show correct title")
        
        # Check main frontend does NOT contain client-specific content
        if check_content_in_file(main_index, "Mycelium Client", "Main frontend should not have client title"):
            issues.append("Main frontend incorrectly shows client interface")
    
    # Check client frontend build exists  
    client_frontend_path = Path("src/mycelium/client_frontend_dist")
    client_index = client_frontend_path / "index.html"
    
    if not check_file_exists(client_index, "Client frontend index.html"):
        issues.append("Client frontend not built")
    else:
        # Check client frontend contains client-specific interface
        if not check_content_in_file(client_index, "🍄 Mycelium Client", "Client frontend title"):
            issues.append("Client frontend doesn't show client interface")
        
        # Check client frontend contains GPU worker content
        if not check_content_in_file(client_index, "GPU worker configuration", "Client frontend description"):
            issues.append("Client frontend missing GPU worker description")
    
    # Check static asset directories
    main_next_dir = main_frontend_path / "_next"
    client_next_dir = client_frontend_path / "_next"
    
    check_file_exists(main_next_dir, "Main frontend _next directory")
    check_file_exists(client_next_dir, "Client frontend _next directory")
    
    # Check app.py has been updated
    app_py_path = Path("src/mycelium/api/app.py")
    if check_file_exists(app_py_path, "Main app.py file"):
        # Check that root endpoint has been moved
        if check_content_in_file(app_py_path, '@app.get("/api")', "API endpoint moved to /api"):
            pass
        elif check_content_in_file(app_py_path, '@app.get("/")', "Root endpoint check"):
            issues.append("Root endpoint still exists at /")
    
    # Check client_app.py has been updated  
    client_app_py_path = Path("src/mycelium/api/client_app.py")
    if check_file_exists(client_app_py_path, "Client app.py file"):
        if not check_content_in_file(client_app_py_path, "client_frontend_dist", "Client app uses client frontend"):
            issues.append("Client app not configured to use client frontend")
    
    print("\n" + "=" * 50)
    
    if issues:
        print("❌ VALIDATION FAILED")
        print("Issues found:")
        for issue in issues:
            print(f"  • {issue}")
        print("\nRecommended fixes:")
        print("  1. Run: ./build_frontend.sh")
        print("  2. Verify both builds completed successfully")
        print("  3. Check that environment variables are set correctly during client build")
        return 1
    else:
        print("✅ VALIDATION PASSED")
        print("Frontend routing fixes are correctly implemented!")
        print("\nNext steps:")
        print("  1. Create wheel: pip wheel .")
        print("  2. Install: pipx install mycelium-*.whl --force")
        print("  3. Test main server: mycelium server (should show full interface at root)")
        print("  4. Test client server: Should show client interface on port 3001")
        return 0


if __name__ == "__main__":
    sys.exit(main())