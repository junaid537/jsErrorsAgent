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
        self.browser = self.playwright.chromium.launch(headless=True)
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


'''





import json
import time
from playwright.sync_api import sync_playwright, ConsoleMessage
from typing import Dict, List, Any, Optional
import os
from datetime import datetime
import re

class ErrorStackCollector:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.error_stacks = {}
        self.rum_errors = None
        # Filter configuration
        self.error_filters = {
            'ignore_csp': True,  # Ignore CSP violations
            'ignore_network': True,  # Ignore network errors
            'ignore_doubleclick': True,  # Ignore doubleclick.net errors
            'min_stack_depth': 2  # Minimum stack trace depth to consider valid
        }

    def start_browser(self):
        """Initialize the browser in headless mode."""
        print("Starting browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']  # Make browser less detectable
        )
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            ignore_https_errors=True  # Ignore certificate errors
        )
        
        # Inject error capturing script before page creation
        self.context.add_init_script("""
            // Capture original error constructor
            const OriginalError = window.Error;
            
            // Store errors globally
            window.__capturedErrors = [];
            
            // Override Error constructor to capture stack traces
            window.Error = function(...args) {
                const error = new OriginalError(...args);
                // Capture the stack trace immediately
                if (Error.captureStackTrace) {
                    Error.captureStackTrace(error, window.Error);
                }
                return error;
            };
            
            // Capture unhandled errors with full stack
            window.addEventListener('error', function(event) {
                const errorInfo = {
                    message: event.message,
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno,
                    stack: event.error ? event.error.stack : 'No stack trace available',
                    timestamp: new Date().toISOString(),
                    type: 'uncaught_error'
                };
                window.__capturedErrors.push(errorInfo);
                console.error('CAPTURED_ERROR:', JSON.stringify(errorInfo));
            }, true);
            
            // Capture unhandled promise rejections
            window.addEventListener('unhandledrejection', function(event) {
                const errorInfo = {
                    message: event.reason ? event.reason.toString() : 'Unhandled Promise Rejection',
                    stack: event.reason && event.reason.stack ? event.reason.stack : 'No stack trace available',
                    timestamp: new Date().toISOString(),
                    type: 'unhandled_rejection'
                };
                window.__capturedErrors.push(errorInfo);
                console.error('CAPTURED_ERROR:', JSON.stringify(errorInfo));
            }, true);
        """)
        
        self.page = self.context.new_page()
        print("Browser started.")

    def setup_error_listeners(self):
        """Set up event listeners for console errors and page errors."""
        print("Setting up error listeners...")
        self.page.on("console", self._handle_console_msg)
        self.page.on("pageerror", self._handle_page_error)
        self.page.on("response", self._handle_response)
        print("Error listeners set up.")

    def _should_ignore_error(self, message: str, stack_trace: str = "") -> bool:
        """Check if an error should be ignored based on filters."""
        message_lower = message.lower()
        
        # Ignore CSP violations
        if self.error_filters['ignore_csp'] and '[report only]' in message_lower:
            return True
            
        # Ignore network errors
        if self.error_filters['ignore_network'] and any(x in message_lower for x in ['failed to load resource', 'net::', 'err_']):
            return True
            
        # Ignore doubleclick errors
        if self.error_filters['ignore_doubleclick'] and 'doubleclick.net' in message:
            return True
            
        # Check stack trace quality
        if stack_trace and self.error_filters['min_stack_depth'] > 0:
            # Count actual stack frames (lines starting with 'at')
            stack_lines = [line for line in stack_trace.split('\n') if line.strip().startswith('at')]
            
            # Ignore if stack only contains Playwright internals
            if all('UtilityScript' in line or 'eval' in line for line in stack_lines):
                return True
                
            # Ignore if stack is too shallow
            if len(stack_lines) < self.error_filters['min_stack_depth']:
                return True
                
        return False

    def _extract_clean_stack_trace(self, error_obj: Any) -> str:
        """Extract and clean stack trace from various error objects."""
        stack_trace = ""
        
        # Try different methods to get stack trace
        if isinstance(error_obj, dict):
            stack_trace = error_obj.get('stack', '')
        elif hasattr(error_obj, 'stack'):
            stack_trace = error_obj.stack
        elif isinstance(error_obj, str) and '\n' in error_obj and 'at ' in error_obj:
            stack_trace = error_obj
            
        # Clean up stack trace
        if stack_trace:
            # Remove Playwright internal frames
            lines = stack_trace.split('\n')
            cleaned_lines = []
            for line in lines:
                if not any(x in line for x in ['UtilityScript', 'eval at evaluate', '__playwright']):
                    cleaned_lines.append(line)
            stack_trace = '\n'.join(cleaned_lines)
            
        return stack_trace

    def _handle_console_msg(self, msg: ConsoleMessage):
        """Handle console messages and capture error details."""
        if msg.type == "error":
            message_text = msg.text
            
            # Check for our custom error format
            if message_text.startswith('CAPTURED_ERROR:'):
                try:
                    # Parse the JSON error data
                    error_data = json.loads(message_text.replace('CAPTURED_ERROR:', '').strip())
                    
                    # Skip if should be ignored
                    if self._should_ignore_error(error_data.get('message', ''), error_data.get('stack', '')):
                        return
                        
                    error_info = {
                        "type": error_data.get('type', 'console_error'),
                        "message": error_data.get('message', ''),
                        "location": {
                            "url": error_data.get('filename', self.page.url),
                            "line": error_data.get('lineno', ''),
                            "column": error_data.get('colno', '')
                        },
                        "timestamp": error_data.get('timestamp', datetime.now().isoformat()),
                        "stack_trace": error_data.get('stack', ''),
                        "user_agent": self.page.evaluate("navigator.userAgent")
                    }
                    
                    self._store_error(error_info)
                    print(f"  -> Captured JavaScript error: {error_info['message'][:100]}...")
                    return
                except json.JSONDecodeError:
                    pass
            
            # Handle regular console errors
            if self._should_ignore_error(message_text):
                return
                
            print(f"Console ERROR detected: {message_text[:100]}...")
            
            location_data = msg.location if hasattr(msg, 'location') and msg.location else {}
            
            # Enhanced stack trace extraction
            stack_trace = ""
            try:
                # Try to get stack from console arguments
                for i, arg in enumerate(msg.args):
                    try:
                        arg_value = arg.json_value()
                        if isinstance(arg_value, dict) and 'stack' in arg_value:
                            stack_trace = self._extract_clean_stack_trace(arg_value)
                            break
                        elif isinstance(arg_value, str) and 'at ' in arg_value:
                            stack_trace = self._extract_clean_stack_trace(arg_value)
                            break
                    except Exception:
                        continue
                        
                # If no stack found, try to get it from the page
                if not stack_trace and 'TypeError' in message_text or 'ReferenceError' in message_text:
                    try:
                        # Extract error details from message
                        match = re.search(r'at\s+(https?://[^\s]+):(\d+):(\d+)', message_text)
                        if match:
                            location_data = {
                                'url': match.group(1),
                                'lineNumber': match.group(2),
                                'columnNumber': match.group(3)
                            }
                            stack_trace = message_text
                    except Exception:
                        pass
                        
            except Exception as e:
                print(f"    -> Error extracting stack trace: {e}")
            
            error_info = {
                "type": "console_error",
                "message": message_text,
                "location": {
                    "url": location_data.get("url", self.page.url),
                    "line": location_data.get("lineNumber", ""),
                    "column": location_data.get("columnNumber", "")
                },
                "timestamp": datetime.now().isoformat(),
                "stack_trace": stack_trace,
                "user_agent": self.page.evaluate("navigator.userAgent")
            }
            
            self._store_error(error_info)
            print(f"  -> Error stored for URL: {self.page.url}")

    def _handle_page_error(self, error):
        """Handle uncaught page errors."""
        error_str = str(error)
        
        if self._should_ignore_error(error_str):
            return
            
        print(f"Page ERROR detected: {error_str[:100]}...")
        
        error_info = {
            "type": "page_error",
            "message": error_str,
            "timestamp": datetime.now().isoformat(),
            "stack_trace": self._extract_clean_stack_trace(error),
            "user_agent": self.page.evaluate("navigator.userAgent")
        }
        
        self._store_error(error_info)
        print(f"  -> Page error stored for URL: {self.page.url}")

    def _handle_response(self, response):
        """Handle HTTP responses to catch 4xx/5xx errors."""
        if response.status >= 400 and self.error_filters.get('capture_http_errors', False):
            print(f"HTTP Error {response.status} for {response.url}")
            # You can store these separately if needed

    def _store_error(self, error_info: Dict[str, Any]):
        """Store error information with the current URL as key."""
        current_url = self.page.url
        
        # Only store errors with meaningful stack traces or messages
        if error_info.get('stack_trace') or 'TypeError' in error_info.get('message', '') or 'ReferenceError' in error_info.get('message', ''):
            if current_url not in self.error_stacks:
                self.error_stacks[current_url] = []
            
            # Avoid duplicate errors
            for existing_error in self.error_stacks[current_url]:
                if (existing_error.get('message') == error_info.get('message') and 
                    existing_error.get('stack_trace') == error_info.get('stack_trace')):
                    return
                    
            self.error_stacks[current_url].append(error_info)

    def collect_error_stacks(self, url: str):
        """Collect error stacks for a given URL."""
        print(f"\nAnalyzing URL: {url}")
        try:
            # Clear previous errors for this URL
            if url in self.error_stacks:
                del self.error_stacks[url]

            # Navigate to the URL
            print(f"Navigating to {url}...")
            response = self.page.goto(url, wait_until="networkidle", timeout=60000)
            print(f"Page loaded with status: {response.status if response else 'N/A'}")

            # Wait for initial JavaScript execution
            time.sleep(2)

            # Retrieve any errors captured by our injected script
            try:
                captured_errors = self.page.evaluate("window.__capturedErrors || []")
                for error in captured_errors:
                    if not self._should_ignore_error(error.get('message', ''), error.get('stack', '')):
                        error_info = {
                            "type": error.get('type', 'captured_error'),
                            "message": error.get('message', ''),
                            "location": {
                                "url": error.get('filename', url),
                                "line": error.get('lineno', ''),
                                "column": error.get('colno', '')
                            },
                            "timestamp": error.get('timestamp', datetime.now().isoformat()),
                            "stack_trace": error.get('stack', ''),
                            "user_agent": self.page.evaluate("navigator.userAgent")
                        }
                        self._store_error(error_info)
                        print(f"  -> Retrieved captured error: {error_info['message'][:100]}...")
            except Exception as e:
                print(f"  -> Could not retrieve captured errors: {e}")

            # Simulate user interactions based on error sources
            self._simulate_user_interaction(url)

            # Final wait and error collection
            print("Waiting for any delayed errors...")
            time.sleep(3)
            
            # One more check for captured errors
            try:
                final_errors = self.page.evaluate("window.__capturedErrors || []")
                # Process any new errors that appeared during interaction
                # (implementation similar to above)
            except Exception:
                pass

        except Exception as e:
            print(f"Error analyzing {url}: {str(e)}")
            if "TimeoutError" not in str(e):  # Don't store timeout errors
                error_info = {
                    "type": "navigation_error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "stack_trace": "",
                    "user_agent": "N/A"
                }
                self._store_error(error_info)

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
                        if submit_button and submit_button.is_visible() and submit_button.is_enabled():
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
            self.generate_summary_report()

        except Exception as e:
            print(f"Error processing URLs: {str(e)}")
            raise
        finally:
            self.close()

    def save_results(self):
        """Save the collected error stacks to a JSON file."""
        output_file = "error_traces.json"
        
        # Prepare data for the desired format
        formatted_error_traces = {}
        for url, errors in self.error_stacks.items():
            formatted_error_traces[url] = []
            for error_info in errors:
                # Only include errors with meaningful stack traces
                if error_info.get("stack_trace") and not all(x in error_info["stack_trace"] for x in ['UtilityScript', 'eval']):
                    formatted_error_traces[url].append({
                        "message": error_info.get("message", ""),
                        "stack_trace": error_info.get("stack_trace", ""),
                        "type": error_info.get("type", ""),
                        "location": error_info.get("location", {})
                    })

        # Remove URLs with no errors
        formatted_error_traces = {k: v for k, v in formatted_error_traces.items() if v}

        with open(output_file, 'w') as f:
            json.dump(formatted_error_traces, f, indent=2)
        print(f"\nError traces saved to {output_file}")

    def generate_summary_report(self):
        """ Generate a summary report of captured errors."""
        print("\n=== ERROR CAPTURE SUMMARY ===")
        
        total_urls = len(self.rum_errors)
        urls_with_errors = len([url for url, errors in self.error_stacks.items() if errors])
        total_errors = sum(len(errors) for errors in self.error_stacks.values())
        
        print(f"Total URLs processed: {total_urls}")
        print(f"URLs with captured errors: {urls_with_errors}")
        print(f"Total errors captured: {total_errors}")
        
        # Count error types
        error_types = {}
        for errors in self.error_stacks.values():
            for error in errors:
                error_type = error.get('type', 'unknown')
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        print("\nError types captured:")
        for error_type, count in error_types.items():
            print(f"  - {error_type}: {count}")
        
        # Find most common errors
        error_messages = {}
        for errors in self.error_stacks.values():
            for error in errors:
                msg = error.get('message', '')
                # Normalize similar messages
                if 'Cannot read properties of null' in msg:
                    msg = "Cannot read properties of null"
                elif 'Cannot read properties of undefined' in msg:
                    msg = "Cannot read properties of undefined"
                error_messages[msg] = error_messages.get(msg, 0) + 1
        
        print("\nMost common errors:")
        for msg, count in sorted(error_messages.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {msg[:80]}... ({count} occurrences)")

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