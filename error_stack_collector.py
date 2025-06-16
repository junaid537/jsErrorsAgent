import json
import time
from playwright.sync_api import sync_playwright
from typing import Dict, List, Any
import os
from datetime import datetime

class ErrorStackCollector:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.error_stacks = {}
        self.rum_errors = None

    def start_browser(self):
        """Initialize the browser in headless mode."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        )
        self.page = self.context.new_page()

    def setup_error_listeners(self):
        """Set up event listeners for console errors and page errors."""
        self.page.on("console", self._handle_console_msg)
        self.page.on("pageerror", self._handle_page_error)

    def _handle_console_msg(self, msg):
        """Handle console messages and capture error details."""
        if msg.type == "error":
            error_info = {
                "type": "console_error",
                "message": msg.text,
                "location": {
                    "url": msg.location.get("url", ""),
                    "line": msg.location.get("lineNumber", ""),
                    "column": msg.location.get("columnNumber", "")
                },
                "timestamp": datetime.now().isoformat(),
                "stack_trace": msg.stack or "",
                "user_agent": self.page.evaluate("navigator.userAgent")
            }
            self._store_error(error_info)

    def _handle_page_error(self, error):
        """Handle uncaught page errors."""
        error_info = {
            "type": "page_error",
            "message": str(error),
            "timestamp": datetime.now().isoformat(),
            "stack_trace": error.stack or "",
            "user_agent": self.page.evaluate("navigator.userAgent")
        }
        self._store_error(error_info)

    def _store_error(self, error_info: Dict[str, Any]):
        """Store error information with the current URL as key."""
        current_url = self.page.url
        if current_url not in self.error_stacks:
            self.error_stacks[current_url] = []
        self.error_stacks[current_url].append(error_info)

    def _simulate_user_interaction(self, url: str):
        """Simulate user interactions based on error sources from RUM data."""
        try:
            # Get error sources for this URL from RUM data
            url_errors = self.rum_errors.get(url, [])
            
            for error in url_errors:
                error_source = error.get("error_source", "")
                
                # Handle different types of error sources
                if "HTMLButtonElement" in error_source:
                    # Simulate button clicks
                    self._simulate_button_clicks()
                
                elif "a._onFocus" in error_source:
                    # Simulate focus events
                    self._simulate_focus_events()
                
                elif "a._onInvalid" in error_source:
                    # Simulate form validation
                    self._simulate_form_validation()
                
                elif "Object.handleValueChange" in error_source:
                    # Simulate input value changes
                    self._simulate_input_changes()
                
                elif "nn._initializeBackDrop" in error_source:
                    # Simulate modal/backdrop interactions
                    self._simulate_modal_interactions()
                
                # Add a small delay between different interactions
                time.sleep(2)

        except Exception as e:
            print(f"Error during user interaction simulation: {str(e)}")

    def _simulate_button_clicks(self):
        """Simulate clicking various buttons on the page."""
        button_selectors = [
            "button", 
            "[role='button']",
            ".btn",
            ".button",
            "input[type='submit']"
        ]
        for selector in button_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    elements[0].click()
                    time.sleep(1)
            except:
                continue

    def _simulate_focus_events(self):
        """Simulate focus events on form elements."""
        focus_selectors = [
            "input",
            "textarea",
            "select",
            "[contenteditable='true']"
        ]
        for selector in focus_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    elements[0].focus()
                    time.sleep(1)
            except:
                continue

    def _simulate_form_validation(self):
        """Simulate form validation by submitting forms with invalid data."""
        try:
            forms = self.page.query_selector_all("form")
            for form in forms:
                try:
                    # Find required inputs and leave them empty
                    required_inputs = form.query_selector_all("[required]")
                    for input_elem in required_inputs:
                        input_elem.fill("")
                    
                    # Try to submit the form
                    form.evaluate("form => form.submit()")
                    time.sleep(1)
                except:
                    continue
        except:
            pass

    def _simulate_input_changes(self):
        """Simulate input value changes."""
        input_selectors = [
            "input[type='text']",
            "input[type='email']",
            "input[type='number']",
            "textarea"
        ]
        for selector in input_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    elements[0].fill("test value")
                    time.sleep(1)
            except:
                continue

    def _simulate_modal_interactions(self):
        """Simulate modal/backdrop interactions."""
        try:
            # Try to find and close modals
            modal_selectors = [
                ".modal",
                ".dialog",
                "[role='dialog']",
                ".backdrop"
            ]
            for selector in modal_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        # Try to click close buttons
                        close_buttons = elements[0].query_selector_all(".close, .modal-close, [aria-label='Close']")
                        if close_buttons and len(close_buttons) > 0:
                            close_buttons[0].click()
                        time.sleep(1)
                except:
                    continue
        except:
            pass

    def collect_error_stacks(self, url: str):
        """Collect error stacks for a given URL."""
        print(f"\nAnalyzing URL: {url}")
        try:
            # Clear previous errors for this URL
            if url in self.error_stacks:
                del self.error_stacks[url]

            # Navigate to the URL
            response = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            print(f"Page loaded with status: {response.status if response else 'N/A'}")

            # Wait for initial page load
            time.sleep(5)

            # Simulate user interactions based on error sources
            self._simulate_user_interaction(url)

            # Additional wait for any delayed errors
            time.sleep(5)

        except Exception as e:
            print(f"Error analyzing {url}: {str(e)}")
            error_info = {
                "type": "navigation_error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
                "stack_trace": str(e),
                "user_agent": self.page.evaluate("navigator.userAgent")
            }
            self._store_error(error_info)

    def process_urls_from_json(self, json_file_path: str):
        """Process all URLs from the JSON file."""
        try:
            # Load RUM errors data
            with open(json_file_path, 'r') as f:
                self.rum_errors = json.load(f)

            # Initialize browser
            self.start_browser()
            self.setup_error_listeners()

            # Process each URL
            for url in self.rum_errors.keys():
                self.collect_error_stacks(url)

            # Save results
            self.save_results()

        except Exception as e:
            print(f"Error processing URLs: {str(e)}")
        finally:
            self.close()

    def save_results(self):
        """Save the collected error stacks to a JSON file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"error_stacks_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(self.error_stacks, f, indent=2)
        print(f"\nError stacks saved to {output_file}")

    def close(self):
        """Clean up browser resources."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

def collect_error_stacks():
    """Function to be called from main.py"""
    collector = ErrorStackCollector()
    collector.process_urls_from_json("rum_errors_by_url.json")
    return collector.error_stacks 