"""
Lambda packaging script for Bedrock-based deployment
Creates a deployment package without sentence-transformers (uses Bedrock Titan embeddings)
"""

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# Configuration
PROJECT_ROOT = Path(__file__).parent
INGESTION_DIR = PROJECT_ROOT / "ingestion"
LAMBDA_ZIP_PATH = INGESTION_DIR / "lambda_deployment.zip"
TEMP_PACKAGE_DIR = PROJECT_ROOT / "lambda_package_temp"

# Files and directories to include
# Files to copy to root of zip (Lambda handler must be at root)
ROOT_FILES = [
    "ingestion/lambda_handler.py",  # Will be copied as lambda_handler.py at root
]

# Files to copy maintaining directory structure
FILES_TO_COPY = [
    # Ingestion files (except lambda_handler which goes to root)
    "ingestion/pdf_extractor.py",
    "ingestion/cv_embedder.py",
    "ingestion/__init__.py",
    
    # Services (only what Lambda needs)
    "services/cv_processor.py",
    "services/__init__.py",
    
    # Utils
    "utils/bedrock_client.py",
    "utils/database.py",
    "utils/__init__.py",
    
    # Models
    "models/candidate.py",
    "models/__init__.py",
    
    # Config
    "config.py",
]

# Directories to create and copy
DIRS_TO_COPY = {
    "services": ["cv_processor.py", "__init__.py"],
    "utils": ["bedrock_client.py", "database.py", "__init__.py"],
    "models": ["candidate.py", "__init__.py"],
}

# Dependencies for Bedrock (no sentence-transformers, no torch)
BEDROCK_DEPENDENCIES = [
    "boto3>=1.34.0",
    "psycopg2-binary>=2.9.9",
    "pgvector>=0.2.4",
    "pypdf>=3.17.0",
    "pydantic[email]>=2.5.0",
    "python-dotenv>=1.0.0",
    "numpy>=1.24.0",
]

# Files/directories to exclude from zip
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".git",
    ".gitignore",
    "*.zip",
    "venv",
    ".venv",
    "env",
    ".env",
    "*.log",
    ".DS_Store",
    "Thumbs.db",
    "*.md",
    "test_*",
    "*_test.py",
    "*.txt",  # Exclude requirements files
]


def clean_temp_dir():
    """Remove temporary packaging directory"""
    if TEMP_PACKAGE_DIR.exists():
        print(f"🧹 Cleaning up {TEMP_PACKAGE_DIR}...")
        shutil.rmtree(TEMP_PACKAGE_DIR)
    TEMP_PACKAGE_DIR.mkdir(parents=True, exist_ok=True)


def copy_source_files():
    """Copy necessary Python source files"""
    print("📁 Copying source files...")
    
    # First, copy lambda_handler.py to root (Lambda requires handler at root)
    # Lambda handler path is configured as "lambda_handler.lambda_handler"
    print("  Copying lambda_handler.py to root...")
    lambda_handler_src = PROJECT_ROOT / "ingestion/lambda_handler.py"
    if lambda_handler_src.exists():
        lambda_handler_dst = TEMP_PACKAGE_DIR / "lambda_handler.py"
        
        # Read the source file and fix imports for root-level location
        with open(lambda_handler_src, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix the sys.path.append - remove one level since we're at root now
        # Original: sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        # New: sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        content = content.replace(
            "sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))",
            "sys.path.append(os.path.dirname(os.path.abspath(__file__)))"
        )
        
        # Write the modified content
        with open(lambda_handler_dst, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"  ✓ Copied lambda_handler.py to root (imports adjusted)")
    else:
        print(f"  ⚠️  Warning: ingestion/lambda_handler.py not found!")
    
    # Copy other files maintaining directory structure
    for file_path in FILES_TO_COPY:
        src = PROJECT_ROOT / file_path
        if not src.exists():
            print(f"  ⚠️  Warning: {file_path} not found, skipping...")
            continue
        
        # Maintain directory structure
        dst = TEMP_PACKAGE_DIR / file_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(src, dst)
        print(f"  ✓ Copied {file_path}")


def install_dependencies():
    """Install Lambda dependencies (Bedrock-compatible only)"""
    print("\n📦 Installing dependencies (Bedrock-compatible)...")
    print("   Excluding: sentence-transformers, torch (using Bedrock Titan embeddings)")
    print("   ⚠️  IMPORTANT: Building on Windows may cause Linux compatibility issues")
    print("   Consider using Docker or WSL for more reliable packaging")
    print()
    
    # Install all dependencies together to handle dependencies correctly
    print("   Installing all dependencies together...")
    try:
        # First, try installing with platform flag for Linux compatibility
        # This is the preferred method but may not work on all systems
        cmd = [
            sys.executable, "-m", "pip", "install",
            *BEDROCK_DEPENDENCIES,
            "-t", str(TEMP_PACKAGE_DIR),
            "--platform", "manylinux2014_x86_64",
            "--only-binary=:all:",
            "--python-version", "3.11",
            "--implementation", "cp",
            "--upgrade",
            "--quiet"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print("   ⚠️  Platform-specific install failed, trying standard install...")
            print("   (This may cause Windows/Linux compatibility issues)")
            raise subprocess.CalledProcessError(result.returncode, cmd)
        
        print("   ✓ Dependencies installed with Linux platform compatibility")
        
    except (subprocess.CalledProcessError, Exception) as e:
        # Fallback: Install without platform flag
        # WARNING: This may include Windows-specific code that won't work on Lambda
        print("   ⚠️  Installing without platform flag (may have compatibility issues)...")
        print("   If you encounter 'os.add_dll_directory' errors, use Docker/WSL to build")
        
        try:
            subprocess.run(
                [
                    sys.executable, "-m", "pip", "install",
                    *BEDROCK_DEPENDENCIES,
                    "-t", str(TEMP_PACKAGE_DIR),
                    "--upgrade",
                    "--quiet"
                ],
                check=True,
                capture_output=True,
                text=True
            )
            print("   ✓ Dependencies installed (standard method)")
            
            # Fix numpy Windows compatibility issue
            fix_numpy_import()
            
        except subprocess.CalledProcessError as e2:
            print(f"   ❌ Failed to install dependencies")
            if e2.stderr:
                print(f"   Error: {e2.stderr}")
            raise


def fix_numpy_import():
    """Fix numpy's Windows-specific DLL handling code for Linux compatibility"""
    numpy_init = TEMP_PACKAGE_DIR / "numpy" / "__init__.py"
    if not numpy_init.exists():
        return
    
    print("   🔧 Fixing numpy import for Linux compatibility...")
    try:
        with open(numpy_init, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if the problematic code exists
        if 'os.add_dll_directory' in content and '_delvewheel_patch' in content:
            # Find and replace the problematic function
            # Pattern to match the _delvewheel_patch function
            # Replace it with a no-op version
            pattern = r'def _delvewheel_patch_1_11_1\(\):.*?os\.add_dll_directory\([^)]+\)'
            
            replacement = '''def _delvewheel_patch_1_11_1():
    # Disabled for Linux compatibility - os.add_dll_directory is Windows-only
    pass'''
            
            # Try to replace the function
            new_content = re.sub(
                pattern,
                replacement,
                content,
                flags=re.DOTALL
            )
            
            # If replacement didn't work, try a simpler approach
            if 'os.add_dll_directory' in new_content:
                # Manual line-by-line replacement
                lines = new_content.split('\n')
                new_lines = []
                in_patch_function = False
                indent_level = 0
                
                for line in lines:
                    if 'def _delvewheel_patch_1_11_1' in line:
                        new_lines.append('def _delvewheel_patch_1_11_1():')
                        new_lines.append('    # Disabled for Linux compatibility')
                        new_lines.append('    pass')
                        in_patch_function = True
                        continue
                    elif in_patch_function:
                        # Skip lines until we're out of the function
                        if line.strip() and not line.strip().startswith(' ') and not line.strip().startswith('\t'):
                            # New top-level statement, function ended
                            in_patch_function = False
                            new_lines.append(line)
                        elif 'os.add_dll_directory' in line:
                            # Skip this line
                            continue
                        elif line.strip() == 'pass' or line.strip() == 'return':
                            # End of function
                            in_patch_function = False
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                
                new_content = '\n'.join(new_lines)
            
            # Write the fixed content
            with open(numpy_init, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("   ✓ Fixed numpy import compatibility (removed Windows DLL handling)")
        else:
            print("   ℹ️  No numpy compatibility fix needed")
            
    except Exception as e:
        print(f"   ⚠️  Could not fix numpy import: {e}")
        print("   Consider using Docker/WSL to build the package for better compatibility")


def create_zip_file():
    """Create the Lambda deployment zip file"""
    print(f"\n📦 Creating zip file: {LAMBDA_ZIP_PATH}")
    
    # Remove existing zip if it exists
    if LAMBDA_ZIP_PATH.exists():
        LAMBDA_ZIP_PATH.unlink()
        print("   Removed existing zip file")
    
    # Create zip file
    shutil.make_archive(
        str(LAMBDA_ZIP_PATH).replace('.zip', ''),
        'zip',
        TEMP_PACKAGE_DIR,
    )
    
    # Get file size
    zip_size_mb = LAMBDA_ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"   ✓ Created {LAMBDA_ZIP_PATH.name} ({zip_size_mb:.2f} MB)")


def verify_package_structure():
    """Verify the package has required files"""
    print("\n🔍 Verifying package structure...")
    
    required_files = [
        "lambda_handler.py",  # Must be at root
        "ingestion/pdf_extractor.py",
        "ingestion/cv_embedder.py",
        "services/cv_processor.py",
        "utils/bedrock_client.py",
        "utils/database.py",
        "models/candidate.py",
        "config.py",
    ]
    
    missing_files = []
    with zipfile.ZipFile(LAMBDA_ZIP_PATH, 'r') as zip_ref:
        zip_contents = zip_ref.namelist()
        
        for req_file in required_files:
            found = any(req_file in f for f in zip_contents)
            if not found:
                missing_files.append(req_file)
            else:
                print(f"   ✓ Found {req_file}")
    
    if missing_files:
        print(f"\n   ⚠️  Warning: Missing files: {', '.join(missing_files)}")
    else:
        print("\n   ✅ All required files present!")


def main():
    """Main packaging function"""
    print("=" * 60)
    print("🚀 Lambda Packaging Script (Bedrock-based)")
    print("=" * 60)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Output: {LAMBDA_ZIP_PATH}")
    print()
    
    try:
        # Step 1: Clean up
        clean_temp_dir()
        
        # Step 2: Copy source files
        copy_source_files()
        
        # Step 3: Install dependencies
        install_dependencies()
        
        # Step 4: Create zip file
        create_zip_file()
        
        # Step 5: Verify package structure
        verify_package_structure()
        
        print("\n" + "=" * 60)
        print("✅ Packaging complete!")
        print("=" * 60)
        print(f"\n📦 Deployment package: {LAMBDA_ZIP_PATH}")
        print(f"📏 Size: {LAMBDA_ZIP_PATH.stat().st_size / (1024 * 1024):.2f} MB")
        print("\n📤 Next steps:")
        print(f"   1. Upload to Lambda:")
        print(f"      aws lambda update-function-code \\")
        print(f"        --function-name <your-lambda-function-name> \\")
        print(f"        --zip-file fileb://{LAMBDA_ZIP_PATH}")
        print(f"\n   2. Or use Terraform (if configured)")
        
    except Exception as e:
        print(f"\n❌ Error during packaging: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # Clean up temp directory
        if TEMP_PACKAGE_DIR.exists():
            print(f"\n🧹 Cleaning up temporary directory...")
            shutil.rmtree(TEMP_PACKAGE_DIR)


if __name__ == "__main__":
    main()
