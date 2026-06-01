import sys
import os
import unittest

# Add project root and tools directory to python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tools_dir = os.path.join(project_root, "tools")
sys.path.insert(0, project_root)
sys.path.insert(0, tools_dir)

class TestCORSConfig(unittest.TestCase):
    def test_socialpeta_cors(self):
        from socialpeta_downloader.api import app
        from fastapi.middleware.cors import CORSMiddleware
        
        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls == CORSMiddleware:
                cors_middleware = middleware
                break
                
        self.assertIsNotNone(cors_middleware, "CORSMiddleware not found in socialpeta_downloader app")
        
        options = cors_middleware.options
        origins = options.get("allow_origins", [])
        credentials = options.get("allow_credentials", False)
        
        print(f"\nSocialPeta CORS: origins={origins}, credentials={credentials}")
        
        self.assertEqual(origins, ["http://localhost:3000", "http://127.0.0.1:3000"])
        self.assertTrue(credentials)

    def test_web_scraper_cors(self):
        from web_scraper.app.main import app
        from fastapi.middleware.cors import CORSMiddleware
        
        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls == CORSMiddleware:
                cors_middleware = middleware
                break
                
        self.assertIsNotNone(cors_middleware, "CORSMiddleware not found in web_scraper app")
        
        options = cors_middleware.options
        origins = options.get("allow_origins", [])
        credentials = options.get("allow_credentials", False)
        
        print(f"\nWeb Scraper CORS: origins={origins}, credentials={credentials}")
        
        self.assertEqual(origins, ["http://localhost:3000", "http://127.0.0.1:3000"])
        self.assertTrue(credentials)

if __name__ == '__main__':
    unittest.main()
