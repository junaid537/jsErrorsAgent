'''
error_stack_collector.py:
This file defines a class ErrorStackCollector that leverages Playwright (a browser automation library).
Its main goal is to reproduce and capture detailed information, especially stack traces, for the JavaScript errors identified by parse_rum_js_errors.py.
It operates in headless browser mode, meaning it runs a browser in the background without a visible UI.
It navigates to each URL that had a RUM error.
While navigating, it sets up listeners to capture real-time console errors and uncaught page errors. When an error is caught, it records the error message, its location (file, line, column), a timestamp, the user agent, and most importantly, the JavaScript stack trace.
A key feature is its ability to simulate user interactions (like clicking buttons, filling forms, focusing on inputs, or interacting with modals) on the page. This simulation is dynamically triggered based on the error_source from the RUM data, attempting to replicate the conditions that led to the original error.
After visiting all URLs and attempting to reproduce errors, it compiles all collected error information and their stack traces into a new JSON file, organized by URL.
'''


'''
is error_stack_collector , matching errors from headless browser with errors in JSON file rum_errors_by_url.json for each URL ?


That's a good question to clarify!
The error_stack_collector.py currently does not explicitly "match" or "compare" the errors it captures from the headless browser with the specific error_source entries in rum_errors_by_url.json.
Here's what it does do:
Uses rum_errors_by_url.json for simulation: It reads rum_errors_by_url.json to get the list of URLs and, more importantly, the error_source associated with those RUM errors. It then uses these error_source values to inform and trigger specific user interaction simulations (like clicking buttons if the RUM error suggested a button interaction). The idea is to recreate the conditions that might have led to the original RUM error.
Captures new errors: While it navigates each URL and performs these simulations, it has event listeners active (_handle_console_msg and _handle_page_error). These listeners capture any new console errors or uncaught page errors that occur during that specific headless browser session, regardless of whether they directly correspond to an error already listed in rum_errors_by_url.json.
Stores collected errors: All the errors caught by the headless browser (including their stack traces) are stored in its own self.error_stacks dictionary and then saved to a new JSON file.
So, to be precise: error_stack_collector.py leverages the information from rum_errors_by_url.json to simulate scenarios, but its primary function is to collect fresh, detailed error data (especially stack traces) from the live browser session, not to perform a direct comparison or reconciliation with the previously identified RUM errors.
If you wanted to specifically compare the collected stack traces with the original RUM errors, that would be a separate analysis step.
'''

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
        print("Starting browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        )
        self.page = self.context.new_page()
        print("Browser started.")

    def setup_error_listeners(self):
        """Set up event listeners for console errors and page errors."""
        print("Setting up error listeners...")
        self.page.on("console", self._handle_console_msg)
        self.page.on("pageerror", self._handle_page_error)
        print("Error listeners set up.")

    def _handle_console_msg(self, msg):
        """Handle console messages and capture error details."""
        if msg.type == "error":
            print(f"Console ERROR detected: {msg.text}")
            location_data = msg.location if hasattr(msg, 'location') and msg.location else {}
            user_agent = "N/A"
            try:
                user_agent = self.page.evaluate("navigator.userAgent")
            except Exception:
                pass
            
            stack_trace = ""
            try:
                # Try to get stack trace from the console message args if available
                for arg in msg.args:
                    # Check if the argument is an Error object and has a stack property
                    try:
                        stack_handle = arg.get_property('stack')
                        if stack_handle:
                            stack_trace_value = stack_handle.json_value()
                            if isinstance(stack_trace_value, str):
                                stack_trace = stack_trace_value
                                break
                    except Exception:
                        pass # Continue to next arg if this one fails
                    
                    # Fallback for simpler string arguments that might contain stack info
                    try:
                        arg_value = arg.json_value()
                        if isinstance(arg_value, dict) and 'stack' in arg_value:
                            stack_trace = arg_value['stack']
                            break
                        elif isinstance(arg_value, str) and 'at ' in arg_value:
                            stack_trace = arg_value
                            break
                    except Exception:
                        continue
            except Exception as e:
                print(f"Error extracting stack from console args: {e}")
                pass
            
            # If no stack trace found, try to capture current stack (less ideal, but a fallback)
            if not stack_trace:
                try:
                    stack_trace = self.page.evaluate("(new Error()).stack") or ""
                except Exception:
                    stack_trace = ""
            
            error_info = {
                "type": "console_error",
                "message": msg.text,
                "location": {
                    "url": location_data.get("url", ""),
                    "line": location_data.get("lineNumber", ""),
                    "column": location_data.get("columnNumber", "")
                },
                "timestamp": datetime.now().isoformat(),
                "stack_trace": stack_trace,
                "user_agent": user_agent
            }
            self._store_error(error_info)
            print(f"  -> Error stored for URL: {self.page.url}")

    def _handle_page_error(self, error):
        """Handle uncaught page errors."""
        print(f"Page ERROR detected: {error}")
        user_agent = "N/A"
        try:
            user_agent = self.page.evaluate("navigator.userAgent")
        except Exception:
            pass
            
        error_info = {
            "type": "page_error",
            "message": str(error),
            "timestamp": datetime.now().isoformat(),
            "stack_trace": getattr(error, 'stack', str(error)),
            "user_agent": user_agent
        }
        self._store_error(error_info)
        print(f"  -> Page error stored for URL: {self.page.url}")

    def _store_error(self, error_info: Dict[str, Any]):
        """Store error information with the current URL as key."""
        current_url = self.page.url
        if current_url not in self.error_stacks:
            self.error_stacks[current_url] = []
        self.error_stacks[current_url].append(error_info)

    def _simulate_user_interaction(self, url: str):
        """Simulate user interactions based on error sources from RUM data."""
        print(f"Simulating user interactions for {url}...")
        try:
            url_errors = self.rum_errors.get(url, [])
            
            if not url_errors:
                print(f"  -> No specific RUM error sources for user interaction simulation on {url}.")
                return

            for error in url_errors:
                error_source = error.get("error_source", "")
                print(f"  -> Simulating based on error source: {error_source}")
                
                if "HTMLButtonElement" in error_source:
                    self._simulate_button_clicks()
                
                elif "a._onFocus" in error_source:
                    self._simulate_focus_events()
                
                elif "a._onInvalid" in error_source:
                    self._simulate_form_validation()
                
                elif "Object.handleValueChange" in error_source:
                    self._simulate_input_changes()
                
                elif "nn._initializeBackDrop" in error_source:
                    self._simulate_modal_interactions()
                
                time.sleep(2)

        except Exception as e:
            print(f"Error during user interaction simulation for {url}: {str(e)}")

    def _simulate_button_clicks(self):
        """Simulate clicking various buttons on the page."""
        print("  -> Attempting to simulate button clicks.")
        button_selectors = [
            "button", 
            "[role='button']",
            ".btn",
            ".button",
            "input[type='submit']"
        ]
        for selector in button_selectors:
            try:
                elements = self.page.locator(selector).all()
                if not elements:
                    continue
                    
                element = elements[0]
                if element.is_visible() and element.is_enabled():
                    print(f"    -> Clicking button: {selector}")
                    element.scroll_into_view_if_needed()
                    element.click(timeout=3000)
                    time.sleep(1)
            except Exception as e:
                print(f"  -> Failed to click button with selector '{selector}': {e}")
                continue

    def _simulate_focus_events(self):
        """Simulate focus events on form elements."""
        print("  -> Attempting to simulate focus events.")
        focus_selectors = [
            "input",
            "textarea",
            "select",
            "[contenteditable='true']"
        ]
        for selector in focus_selectors:
            try:
                elements = self.page.locator(selector).all()
                if not elements:
                    continue
                    
                element = elements[0]
                if element.is_visible() and element.is_enabled():
                    print(f"    -> Focusing on element: {selector}")
                    element.focus()
                    time.sleep(1)
            except Exception as e:
                print(f"  -> Failed to focus on element with selector '{selector}': {e}")
                continue

    def _simulate_form_validation(self):
        """Simulate form validation by submitting forms with invalid data."""
        print("  -> Attempting to simulate form validation.")
        try:
            forms = self.page.locator("form").all()
            if not forms:
                print("    -> No forms found for validation.")
                return
                
            for form in forms:
                try:
                    # Find required inputs within this form and leave them empty
                    required_inputs = form.locator("[required]").all()
                    print(f"    -> Found {len(required_inputs)} required inputs in a form.")
                    
                    for input_elem in required_inputs:
                        try:
                            if input_elem.is_visible() and input_elem.is_editable():
                                print(f"      -> Clearing required input")
                                input_elem.fill("")
                        except Exception:
                            continue
                    
                    # Try to submit the form
                    try:
                        if form.is_visible() and form.is_enabled():
                            print("    -> Submitting form for validation.")
                            form.evaluate("form => form.submit()")
                            time.sleep(1)
                    except Exception:
                        # Try alternative submission methods
                        submit_button = form.locator("input[type='submit'], button[type='submit']").first
                        if submit_button.is_visible() and submit_button.is_enabled():
                            submit_button.click()
                            time.sleep(1)
                            
                except Exception as e:
                    print(f"  -> Failed to simulate form validation for form: {e}")
                    continue
        except Exception as e:
            print(f"Error finding forms for validation: {e}")

    def _simulate_input_changes(self):
        """Simulate input value changes."""
        print("  -> Attempting to simulate input changes.")
        input_selectors = [
            "input[type='text']",
            "input[type='email']",
            "input[type='number']",
            "textarea"
        ]
        for selector in input_selectors:
            try:
                elements = self.page.locator(selector).all()
                if not elements:
                    continue
                    
                element = elements[0]
                if element.is_visible() and element.is_editable():
                    print(f"    -> Changing input value: {selector}")
                    element.fill("test value")
                    # Trigger change event
                    element.dispatch_event("change")
                    time.sleep(1)
            except Exception as e:
                print(f"  -> Failed to change input with selector '{selector}': {e}")
                continue

    def _simulate_modal_interactions(self):
        """Simulate modal/backdrop interactions."""
        print("  -> Attempting to simulate modal interactions.")
        try:
            modal_selectors = [
                ".modal",
                ".dialog",
                "[role='dialog']",
                ".backdrop"
            ]
            for selector in modal_selectors:
                try:
                    elements = self.page.locator(selector).all()
                    if not elements:
                        continue
                        
                    element = elements[0]
                    if element.is_visible():
                        print(f"    -> Found visible modal/backdrop: {selector}")
                        # Try to click close buttons within the modal
                        close_buttons = element.locator(".close, .modal-close, [aria-label='Close']").all()
                        if close_buttons:
                            for close_button in close_buttons:
                                try:
                                    if close_button.is_visible() and close_button.is_enabled():
                                        print("      -> Clicking modal close button.")
                                        close_button.scroll_into_view_if_needed()
                                        close_button.click(timeout=3000)
                                        break
                                except Exception:
                                    continue
                        time.sleep(1)
                except Exception as e:
                    print(f"  -> Failed to interact with modal/backdrop with selector '{selector}': {e}")
                    continue
        except Exception as e:
            print(f"Error finding modals for interaction: {e}")

    def collect_error_stacks(self, url: str):
        """Collect error stacks for a given URL."""
        print(f"\nAnalyzing URL: {url}")
        try:
            # Clear previous errors for this URL
            if url in self.error_stacks:
                del self.error_stacks[url]

            # Navigate to the URL and wait for network to be idle
            print(f"Navigating to {url}...")
            response = self.page.goto(url, wait_until="networkidle", timeout=60000)
            print(f"Page loaded with status: {response.status if response else 'N/A'}")

            # Wait a bit for initial errors
            time.sleep(2)

            # Simulate user interactions based on error sources
            self._simulate_user_interaction(url)

            # Additional wait for any delayed errors
            print("Waiting for any delayed errors...")
            time.sleep(3)

        except Exception as e:
            print(f"Error analyzing {url}: {str(e)}")
            error_info = {
                "type": "navigation_error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
                "stack_trace": str(e),
                "user_agent": "N/A" # User agent might not be available if navigation failed early
            }
            self._store_error(error_info)

    def process_urls_from_json(self, json_file_path: str):
        """Process all URLs from the JSON file."""
        print(f"Processing URLs from {json_file_path}...")
        try:
            # Check if file exists
            if not os.path.exists(json_file_path):
                raise FileNotFoundError(f"JSON file not found: {json_file_path}")

            # Load RUM errors data
            with open(json_file_path, 'r') as f:
                self.rum_errors = json.load(f)
            print(f"Loaded {len(self.rum_errors)} URLs from RUM data.")

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
            raise
        finally:
            self.close()

    def save_results(self):
        """Save the collected error stacks to a JSON file."""
        output_file = "error_traces.json"
        
        # Prepare data for the desired format: URL as key, list of {message, stack_trace} as value
        formatted_error_traces = {}
        for url, errors in self.error_stacks.items():
            formatted_error_traces[url] = []
            for error_info in errors:
                formatted_error_traces[url].append({
                    "message": error_info.get("message", ""),
                    "stack_trace": error_info.get("stack_trace", "")
                })

        with open(output_file, 'w') as f:
            json.dump(formatted_error_traces, f, indent=2)
        print(f"\nError traces saved to {output_file}")

    def close(self):
        """Clean up browser resources."""
        print("Closing browser...")
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            print("Browser closed.")
        except Exception as e:
            print(f"Error during cleanup: {e}")

def collect_error_stacks():
    """Function to be called from main.py"""
    collector = ErrorStackCollector()
    collector.process_urls_from_json("rum_errors_by_url.json")
    return collector.error_stacks

# Allow running as standalone script
if __name__ == "__main__":
    collect_error_stacks()







