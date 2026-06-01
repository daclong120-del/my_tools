import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root and scripts directory to python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "scripts"))

class TestBuildConfig(unittest.TestCase):
    @patch('subprocess.run')
    @patch('shutil.copy2')
    @patch('shutil.copytree')
    @patch('shutil.rmtree')
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_build_arguments(self, mock_exists, mock_makedirs, mock_rmtree, mock_copytree, mock_copy2, mock_run):
        # Mock paths and checks
        mock_exists.return_value = True
        
        # Import the build module
        import build
        
        # Run main function
        try:
            build.main()
        except SystemExit:
            pass # Expect sys.exit(0) or similar if packaging fails later, but we focus on pyinstaller command argument verification
            
        # Verify subprocess.run was called for PyInstaller
        pyinstaller_call = None
        for call in mock_run.call_args_list:
            args = call[0][0]
            if isinstance(args, list) and any("pyinstaller" in arg.lower() for arg in args):
                pyinstaller_call = args
                break
                
        self.assertIsNotNone(pyinstaller_call, "PyInstaller subprocess command not found")
        
        # Assert hidden imports are included
        self.assertTrue(any("--hidden-import" in arg for arg in pyinstaller_call), "No hidden imports found")
        
        # Check specific packages
        expected_imports = ["playwright", "psutil", "requests"]
        for pkg in expected_imports:
            # Find the package in the command
            found = False
            for i, arg in enumerate(pyinstaller_call):
                if arg == "--hidden-import" and i + 1 < len(pyinstaller_call) and pyinstaller_call[i+1] == pkg:
                    found = True
                    break
            self.assertTrue(found, f"Missing hidden import: {pkg}")
            
        # Verify collect-all arguments
        expected_collects = ["playwright", "psutil"]
        for pkg in expected_collects:
            found = False
            for i, arg in enumerate(pyinstaller_call):
                if arg == "--collect-all" and i + 1 < len(pyinstaller_call) and pyinstaller_call[i+1] == pkg:
                    found = True
                    break
            self.assertTrue(found, f"Missing --collect-all for: {pkg}")

if __name__ == '__main__':
    unittest.main()
