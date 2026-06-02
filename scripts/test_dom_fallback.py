# scripts/test_dom_fallback.py
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "tools"))

from socialpeta_downloader.core import SocialPetaDownloaderCore

class MockLocator:
    def __init__(self, values):
        self.values = values

    def count(self):
        return len(self.values)

    def nth(self, index):
        mock_el = MagicMock()
        # Set text_content or input_value based on expected call
        mock_el.text_content.return_value = self.values[index]
        mock_el.input_value.return_value = self.values[index]
        return mock_el

class TestDOMFallback(unittest.TestCase):
    def setUp(self):
        self.core = SocialPetaDownloaderCore()

    def test_scrape_app_name_from_tags(self):
        page = MagicMock()
        page.url = "https://www.socialpeta.com/index"
        
        # We mock page.locator to return a MockLocator for specific selectors
        def locator_side_effect(selector):
            if selector == ".ant-select-selection-item":
                return MockLocator(["My Premium App"])
            return MockLocator([])
        
        page.locator.side_effect = locator_side_effect
        
        res = self.core.tab_scanner._scrape_app_name_from_dom(page)
        self.assertEqual(res, "My Premium App")

    def test_scrape_app_name_from_inputs(self):
        page = MagicMock()
        page.url = "https://www.socialpeta.com/index"
        
        # Return empty list for tags, but valid list for input selector
        def locator_side_effect(selector):
            if selector == "input[placeholder*='Search' i]":
                return MockLocator(["Search App Name"])
            return MockLocator([])
            
        page.locator.side_effect = locator_side_effect
        
        res = self.core.tab_scanner._scrape_app_name_from_dom(page)
        self.assertEqual(res, "Search App Name")

    def test_scrape_app_name_from_headers(self):
        page = MagicMock()
        page.url = "https://www.socialpeta.com/index"
        
        # Return empty list for tags and inputs, but valid list for header
        def locator_side_effect(selector):
            if selector == "h1":
                return MockLocator(["Header App Name"])
            return MockLocator([])
            
        page.locator.side_effect = locator_side_effect
        
        res = self.core.tab_scanner._scrape_app_name_from_dom(page)
        self.assertEqual(res, "Header App Name")

    def test_scrape_app_name_from_url(self):
        page = MagicMock()
        # No locators found
        page.locator.return_value = MockLocator([])
        
        # URL has appName query param
        page.url = "https://www.socialpeta.com/index?appName=URLAppName"
        
        res = self.core.tab_scanner._scrape_app_name_from_dom(page)
        self.assertEqual(res, "URLAppName")

    def test_scrape_app_name_all_failed(self):
        page = MagicMock()
        page.locator.return_value = MockLocator([])
        page.url = "https://www.socialpeta.com/index?keyword=socialpeta"
        
        res = self.core.tab_scanner._scrape_app_name_from_dom(page)
        self.assertIsNone(res)

if __name__ == '__main__':
    unittest.main()
