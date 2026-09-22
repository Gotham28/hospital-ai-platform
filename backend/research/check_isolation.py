import ast
import os
import sys
import argparse
import tempfile
import shutil
from pathlib import Path

def get_imported_module_names(filepath):
    names = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=filepath)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.append((alias.name, node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.append((node.module, node.lineno))
    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
    return names

def check_directory(dir_path, forbidden_exact, forbidden_prefixes):
    violations = []
    path = Path(dir_path)
    if not path.exists():
        return violations

    for py_file in path.rglob('*.py'):
        imports = get_imported_module_names(str(py_file))
        for mod_name, lineno in imports:
            if mod_name in forbidden_exact or any(mod_name.startswith(p) for p in forbidden_prefixes):
                violations.append((str(py_file), mod_name, lineno))
    return violations

def run_checks(app_dir, research_dir):
    violations = []
    
    # Check app -> research
    app_violations = check_directory(
        app_dir,
        forbidden_exact={'research', 'backend.research'},
        forbidden_prefixes={'backend.research.', 'research.'}
    )
    for v in app_violations:
        violations.append((v[0], f"app\u2192research violation: imported '{v[1]}' at line {v[2]}"))
        
    # Check research -> app
    research_violations = check_directory(
        research_dir,
        forbidden_exact={'app', 'backend.app'},
        forbidden_prefixes={'backend.app.', 'app.'}
    )
    for v in research_violations:
        violations.append((v[0], f"research\u2192app violation: imported '{v[1]}' at line {v[2]}"))
        
    return violations

def self_test():
    temp_dir = tempfile.mkdtemp()
    try:
        app_dir = Path(temp_dir) / 'app'
        research_dir = Path(temp_dir) / 'research'
        app_dir.mkdir()
        research_dir.mkdir()
        
        # Plant violation in app/
        bad_app_file = app_dir / 'bad.py'
        bad_app_file.write_text("import backend.research\n", encoding='utf-8')
        
        # Plant clean file in research/
        clean_research_file = research_dir / 'clean.py'
        clean_research_file.write_text("import os\n", encoding='utf-8')
        
        # Plant second violation in research/
        bad_research_file = research_dir / 'bad2.py'
        bad_research_file.write_text("from app.core.config import settings\n", encoding='utf-8')
        
        violations = run_checks(str(app_dir), str(research_dir))
        
        has_app_violation = any("app\u2192research violation" in v[1] for v in violations)
        has_research_violation = any("research\u2192app violation" in v[1] for v in violations)
        
        if len(violations) == 2 and has_app_violation and has_research_violation:
            print("Self-test passed: Caught both planted violations successfully.")
            return 0
        else:
            print("Self-test failed: Did not catch all planted violations correctly.")
            if not has_app_violation:
                print("Missed app\u2192research violation.")
            if not has_research_violation:
                print("Missed research\u2192app violation.")
            print("Current violations found:")
            for v in violations:
                print(f"{v[0]}: {v[1]}")
            return 1
    finally:
        shutil.rmtree(temp_dir)

def main():
    parser = argparse.ArgumentParser(description="Check isolation between backend/app and backend/research")
    parser.add_argument("--self-test", action="store_true", help="Run self-test with a planted violation")
    args = parser.parse_args()
    
    if args.self_test:
        sys.exit(self_test())
    
    # Normal mode
    base_dir = Path(__file__).resolve().parent.parent
    app_dir = base_dir / 'app'
    research_dir = base_dir / 'research'
    
    violations = run_checks(str(app_dir), str(research_dir))
    
    if not violations:
        print("Success: Zero isolation violations found.")
        sys.exit(0)
    else:
        for filepath, msg in violations:
            print(f"{filepath}: {msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
