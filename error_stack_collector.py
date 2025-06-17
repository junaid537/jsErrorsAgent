'''
import json
import time
from playwright.sync_api import sync_playwright, ConsoleMessage
from typing import Dict, List, Any, Optional
import os
from datetime import datetime
import re

class DiagnosticErrorCollector:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.error_stacks = {} # Store what's considered JS errors
        self.all_errors = {}  # Store ALL errors before filtering
        self.filtered_errors = {}  # Store what was filtered out
        self.rum_errors = None
        self.stats = {
            'total_console_errors': 0,
            'total_page_errors': 0,
            'csp_violations': 0,
            'network_errors': 0,
            'javascript_errors': 0,
            'filtered_out': 0
        }

    def start_browser(self, headless=True):
        """Initialize the browser."""
        print(f"Starting browser in {'headless' if headless else 'headful'} mode...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=headless,
            slow_mo=0 if headless else 300,  # Slow down in headful mode
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            ignore_https_errors=True
        )
        
        # Inject comprehensive error capturing script
        self.context.add_init_script("""
            // Store all types of errors
            window.__allErrors = [];
            window.__jsErrors = [];
            
            // Capture error events
            window.addEventListener('error', function(event) {
                const errorInfo = {
                    type: 'error_event',
                    message: event.message,
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno,
                    stack: event.error ? event.error.stack : 'No stack trace',
                    timestamp: new Date().toISOString(),
                    error: event.error
                };
                window.__allErrors.push(errorInfo);
                
                // Check if it's a real JS error
                if (event.error && event.error.stack && !event.message.includes('[Report Only]')) {
                    window.__jsErrors.push(errorInfo);
                    console.error('JS_ERROR_CAPTURED:', JSON.stringify(errorInfo));
                }
            }, true);
            
            // Capture unhandled promise rejections
            window.addEventListener('unhandledrejection', function(event) {
                const errorInfo = {
                    type: 'unhandled_rejection',
                    message: event.reason ? event.reason.toString() : 'Unhandled Promise Rejection',
                    stack: event.reason && event.reason.stack ? event.reason.stack : 'No stack trace',
                    timestamp: new Date().toISOString()
                };
                window.__allErrors.push(errorInfo);
                window.__jsErrors.push(errorInfo);
                console.error('JS_ERROR_CAPTURED:', JSON.stringify(errorInfo));
            }, true);
            
            // Monitor console.error calls
            const originalConsoleError = console.error;
            console.error = function(...args) {
                const errorInfo = {
                    type: 'console_error_direct',
                    message: args.join(' '),
                    timestamp: new Date().toISOString()
                };
                window.__allErrors.push(errorInfo);
                originalConsoleError.apply(console, args);
            };
        """)
        
        self.page = self.context.new_page()
        print("Browser started.")

    def setup_error_listeners(self):
        """Set up event listeners for console errors and page errors."""
        print("Setting up error listeners...")
        self.page.on("console", self._handle_console_msg)
        self.page.on("pageerror", self._handle_page_error)
        print("Error listeners set up.")

    def _categorize_error(self, message: str, stack_trace: str = "") -> str:
        """Categorize the type of error."""
        message_lower = message.lower()
        
        if '[report only]' in message_lower:
            return 'csp_violation'
        elif any(x in message_lower for x in ['failed to load resource', 'net::', 'err_']):
            return 'network_error'
        elif 'doubleclick.net' in message:
            return 'ad_blocker'
        elif stack_trace and any(x in stack_trace for x in ['TypeError', 'ReferenceError', 'SyntaxError']):
            return 'javascript_error'
        elif 'cannot read' in message_lower or 'undefined' in message_lower or 'null' in message_lower:
            return 'javascript_error'
        else:
            return 'other'

    def _handle_console_msg(self, msg: ConsoleMessage):
        """Handle console messages and capture error details."""
        if msg.type == "error":
            self.stats['total_console_errors'] += 1
            message_text = msg.text
            
            # Special handling for our captured errors
            if message_text.startswith('JS_ERROR_CAPTURED:'):
                try:
                    error_data = json.loads(message_text.replace('JS_ERROR_CAPTURED:', '').strip())
                    self._store_error(error_data, filtered=False)
                    print(f"  ✓ Captured JavaScript error: {error_data.get('message', '')[:80]}...")
                    return
                except:
                    pass
            
            # Categorize the error
            error_category = self._categorize_error(message_text)
            
            # Update stats
            if error_category == 'csp_violation':
                self.stats['csp_violations'] += 1
            elif error_category == 'network_error':
                self.stats['network_errors'] += 1
            elif error_category == 'javascript_error':
                self.stats['javascript_errors'] += 1
            
            print(f"  [{error_category.upper()}] {message_text[:100]}...")
            
            # Get location and stack trace
            location_data = msg.location if hasattr(msg, 'location') and msg.location else {}
            stack_trace = ""
            
            # Try to extract stack trace
            try:
                for arg in msg.args:
                    try:
                        arg_value = arg.json_value()
                        if isinstance(arg_value, dict) and 'stack' in arg_value:
                            stack_trace = arg_value.get('stack', '')
                            break
                        elif isinstance(arg_value, str) and 'at ' in arg_value:
                            stack_trace = arg_value
                            break
                    except:
                        continue
                        
                # Extract location from message if available
                if not location_data and 'at https://' in message_text:
                    match = re.search(r'at\s+(https?://[^\s]+):(\d+):(\d+)', message_text)
                    if match:
                        location_data = {
                            'url': match.group(1),
                            'lineNumber': match.group(2),
                            'columnNumber': match.group(3)
                        }
                        if not stack_trace:
                            stack_trace = message_text
            except:
                pass
            
            error_info = {
                "type": "console_error",
                "category": error_category,
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
            
            # Store in all_errors
            self._store_error(error_info, filtered=False, category='all')
            
            # Store in filtered or main based on category
            if error_category in ['csp_violation', 'network_error', 'ad_blocker']:
                self._store_error(error_info, filtered=True)
                self.stats['filtered_out'] += 1
            else:
                self._store_error(error_info, filtered=False)

    def _handle_page_error(self, error):
        """Handle uncaught page errors."""
        self.stats['total_page_errors'] += 1
        error_str = str(error)
        error_category = self._categorize_error(error_str, str(error))
        
        if error_category == 'javascript_error':
            self.stats['javascript_errors'] += 1
        
        print(f"  [PAGE ERROR - {error_category.upper()}] {error_str[:100]}...")
        
        error_info = {
            "type": "page_error",
            "category": error_category,
            "message": error_str,
            "timestamp": datetime.now().isoformat(),
            "stack_trace": getattr(error, 'stack', str(error)),
            "user_agent": self.page.evaluate("navigator.userAgent")
        }
        
        # Store in all_errors
        self._store_error(error_info, filtered=False, category='all')
        
        # Only store JavaScript errors in main collection
        if error_category == 'javascript_error':
            self._store_error(error_info, filtered=False)
        else:
            self._store_error(error_info, filtered=True)
            self.stats['filtered_out'] += 1

    def _handle_response(self, response):
        """Handle HTTP responses to catch 4xx/5xx errors."""
        if response.status >= 400 and self.error_filters.get('capture_http_errors', False):
            print(f"HTTP Error {response.status} for {response.url}")
            # You can store these separately if needed

    def _store_error(self, error_info: Dict[str, Any], filtered: bool = False, category: str = 'main'):
        """Store error information."""
        current_url = self.page.url
        
        if category == 'all':
            if current_url not in self.all_errors:
                self.all_errors[current_url] = []
            self.all_errors[current_url].append(error_info)
        elif filtered:
            if current_url not in self.filtered_errors:
                self.filtered_errors[current_url] = []
            self.filtered_errors[current_url].append(error_info)
        else:
            if current_url not in self.error_stacks:
                self.error_stacks[current_url] = []
            self.error_stacks[current_url].append(error_info)

    def collect_error_stacks(self, url: str):
        """Collect error stacks for a given URL."""
        print(f"\n{'='*60}")
        print(f"Analyzing URL: {url}")
        print(f"{'='*60}")
        
        try:
            # Navigate to the URL
            print(f"Navigating to {url}...")
            response = self.page.goto(url, wait_until="networkidle", timeout=60000)
            print(f"Page loaded with status: {response.status if response else 'N/A'}")

            # Wait for initial JavaScript execution
            time.sleep(3)

            # Check for errors captured by our injected script
            try:
                all_errors = self.page.evaluate("window.__allErrors || []")
                js_errors = self.page.evaluate("window.__jsErrors || []")
                
                print(f"\nInjected script captured:")
                print(f"  - Total errors: {len(all_errors)}")
                print(f"  - JavaScript errors: {len(js_errors)}")
                
                for error in js_errors:
                    error_info = {
                        "type": error.get('type', 'captured_error'),
                        "category": "javascript_error",
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
                    self._store_error(error_info, filtered=False)
                    print(f"  ✓ Captured JS error: {error_info['message'][:80]}...")
            except Exception as e:
                print(f"  ! Could not retrieve injected script errors: {e}")

            # Simulate user interactions if needed
            if url in self.rum_errors and self.rum_errors[url]:
                print("\nSimulating user interactions based on RUM data...")
                self._simulate_user_interaction(url)
                time.sleep(2)

            # Final error check
            print("\nFinal error check...")
            time.sleep(2)

        except Exception as e:
            print(f"! Error analyzing {url}: {str(e)}")
            error_info = {
                "type": "navigation_error",
                "category": "navigation_error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
                "stack_trace": "",
                "user_agent": "N/A"
            }
            self._store_error(error_info, filtered=False)

    def _simulate_user_interaction(self, url: str):
        """Simulate user interactions based on error sources from RUM data."""
        url_errors = self.rum_errors.get(url, [])
        
        for error in url_errors:
            error_source = error.get("error_source", "")
            print(f"  - Simulating based on error source: {error_source}")
            
            try:
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
            except Exception as e:
                print(f"    ! Simulation error: {e}")

    def _simulate_button_clicks(self):
        """Simulate clicking buttons."""
        try:
            buttons = self.page.locator("button, [role='button'], .btn, .button").all()[:3]  # Limit to first 3
            for button in buttons:
                if button.is_visible() and button.is_enabled():
                    button.click(timeout=2000)
                    time.sleep(1)
        except:
            pass

    def _simulate_focus_events(self):
        """Simulate focus events."""
        try:
            inputs = self.page.locator("input, textarea, select").all()[:3]  # Limit to first 3
            for input_elem in inputs:
                if input_elem.is_visible() and input_elem.is_enabled():
                    input_elem.focus()
                    time.sleep(0.5)
        except:
            pass

    def _simulate_form_validation(self):
        """Simulate form validation."""
        try:
            forms = self.page.locator("form").all()[:2]  # Limit to first 2 forms
            for form in forms:
                required_inputs = form.locator("[required]").all()
                for input_elem in required_inputs[:3]:  # Limit inputs per form
                    if input_elem.is_visible() and input_elem.is_editable():
                        input_elem.fill("")
                # Try to submit
                try:
                    form.evaluate("form => form.submit()")
                except:
                    pass
                time.sleep(1)
        except:
            pass

    def _simulate_input_changes(self):
        """Simulate input changes."""
        try:
            inputs = self.page.locator("input[type='text'], textarea").all()[:3]
            for input_elem in inputs:
                if input_elem.is_visible() and input_elem.is_editable():
                    input_elem.fill("test")
                    input_elem.dispatch_event("change")
                    time.sleep(0.5)
        except:
            pass

    def _simulate_modal_interactions(self):
        """Simulate modal interactions."""
        try:
            modals = self.page.locator(".modal, .dialog, [role='dialog']").all()
            for modal in modals[:2]:
                if modal.is_visible():
                    close_btn = modal.locator(".close, .modal-close").first
                    if close_btn and close_btn.is_visible():
                        close_btn.click(timeout=2000)
                        time.sleep(1)
        except:
            pass

    def process_urls_from_json(self, json_file_path: str):
        """Process all URLs from the JSON file."""
        print(f"Processing URLs from {json_file_path}...")
        
        try:
            if not os.path.exists(json_file_path):
                raise FileNotFoundError(f"JSON file not found: {json_file_path}")

            with open(json_file_path, 'r') as f:
                self.rum_errors = json.load(f)
            print(f"Loaded {len(self.rum_errors)} URLs from RUM data.")

            # Initialize browser
            self.start_browser(headless=True)  # Change to False to see browser
            self.setup_error_listeners()

            # Process each URL
            for i, url in enumerate(self.rum_errors.keys(), 1):
                print(f"\n[{i}/{len(self.rum_errors)}] Processing...")
                self.collect_error_stacks(url)

            # Save all results
            self.save_all_results()
            self.print_summary()

        except Exception as e:
            print(f"Error processing URLs: {str(e)}")
            raise
        finally:
            self.close()

    def save_all_results(self):
        """Save all collected data."""
        # Save JavaScript errors only (main output)
        output_file = "error_traces.json"
        formatted_error_traces = {}
        
        for url, errors in self.error_stacks.items():
            formatted_error_traces[url] = []
            for error_info in errors:
                if error_info.get("category") == "javascript_error" or not error_info.get("category"): # Also include uncategorized errors that make it through
                    formatted_error_traces[url].append({
                        "message": error_info.get("message", ""),
                        "stack_trace": error_info.get("stack_trace", ""),
                        "type": error_info.get("type", ""),
                        "location": error_info.get("location", {})
                    })
        
        # Remove empty URLs
        formatted_error_traces = {k: v for k, v in formatted_error_traces.items() if v}
        
        with open(output_file, 'w') as f:
            json.dump(formatted_error_traces, f, indent=2)
        print(f"\nJavaScript errors saved to {output_file}")
        
        # Save diagnostic data
        diagnostic_data = {
            "summary": {
                "total_urls": len(self.rum_errors),
                "urls_with_js_errors": len(formatted_error_traces),
                "stats": self.stats
            },
            "all_errors": self.all_errors,
            "filtered_errors": self.filtered_errors,
            "javascript_errors": formatted_error_traces
        }
        
        with open("diagnostic_error_report.json", 'w') as f:
            json.dump(diagnostic_data, f, indent=2)
        print("Diagnostic report saved to diagnostic_error_report.json")

    def print_summary(self):
        """Print a comprehensive summary."""
        print(f"\n{'='*60}")
        print("COLLECTION SUMMARY")
        print(f"{'='*60}")
        print(f"Total URLs processed: {len(self.rum_errors)}")
        print(f"URLs with JavaScript errors: {len([url for url, errors in self.error_stacks.items() if errors])}")
        print(f"\nError Statistics:")
        print(f"  - Total console errors seen: {self.stats['total_console_errors']}")
        print(f"  - Total page errors seen: {self.stats['total_page_errors']}")
        print(f"  - CSP violations: {self.stats['csp_violations']}")
        print(f"  - Network errors: {self.stats['network_errors']}")
        print(f"  - JavaScript errors: {self.stats['javascript_errors']}")
        print(f"  - Errors filtered out: {self.stats['filtered_out']}")
        
        print(f"\nURLs with JavaScript errors:")
        for url, errors in self.error_stacks.items():
            if errors:
                js_errors = [e for e in errors if e.get('category') == 'javascript_error']
                if js_errors:
                    print(f"  - {url}: {len(js_errors)} JS errors")

    def close(self):
        """Clean up browser resources."""
        print("\nClosing browser...")
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

def run_diagnostic_collection():
    """Run the diagnostic collection."""
    collector = DiagnosticErrorCollector()
    collector.process_urls_from_json("rum_errors_by_url.json")
    return collector.error_stacks

if __name__ == "__main__":
    run_diagnostic_collection()
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
        self.user_agent = None  # Cache user agent to avoid repeated evaluations

    def start_browser(self):
        """Initialize the browser in headless mode."""
        print("Starting browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
            ignore_https_errors=True
        )
        
        # Cache the user agent string
        self.user_agent = self.context.user_agent
        
        # Inject error capturing script
        self.context.add_init_script("""
            // Store errors globally
            window.__capturedErrors = [];
            
            // Capture error events
            window.addEventListener('error', function(event) {
                const errorInfo = {
                    type: 'error_event',
                    message: event.message,
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno,
                    stack: event.error ? event.error.stack : 'No stack trace',
                    timestamp: new Date().toISOString()
                };
                window.__capturedErrors.push(errorInfo);
                console.error('CAPTURED_ERROR:', JSON.stringify(errorInfo));
            }, true);
            
            // Capture unhandled promise rejections
            window.addEventListener('unhandledrejection', function(event) {
                const errorInfo = {
                    type: 'unhandled_rejection',
                    message: event.reason ? event.reason.toString() : 'Unhandled Promise Rejection',
                    stack: event.reason && event.reason.stack ? event.reason.stack : 'No stack trace',
                    timestamp: new Date().toISOString()
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
        print("Error listeners set up.")

    def _safe_evaluate(self, expression: str, default_value: Any = None) -> Any:
        """Safely evaluate JavaScript expressions, handling navigation errors."""
        try:
            return self.page.evaluate(expression)
        except Exception as e:
            if "Execution context was destroyed" in str(e):
                print(f"  ! Navigation detected, returning default value for: {expression}")
                return default_value
            else:
                print(f"  ! Error evaluating {expression}: {e}")
                return default_value

    def _get_user_agent(self) -> str:
        """Get user agent, using cached value if page context is destroyed."""
        if self.user_agent:
            return self.user_agent
        
        user_agent = self._safe_evaluate("navigator.userAgent", "N/A")
        if user_agent != "N/A":
            self.user_agent = user_agent
        return user_agent

    def _should_ignore_error(self, message: str, stack_trace: str = "") -> bool:
        """Check if an error should be ignored based on filters."""
        message_lower = message.lower()
        
        # Ignore CSP violations
        if '[report only]' in message_lower:
            return True
            
        # Ignore network errors
        if any(x in message_lower for x in ['failed to load resource', 'net::', 'err_']):
            return True
            
        # Ignore doubleclick errors
        if 'doubleclick.net' in message:
            return True
            
        # Check stack trace quality
        if stack_trace:
            # Count actual stack frames
            stack_lines = [line for line in stack_trace.split('\n') if line.strip().startswith('at')]
            
            # Ignore if stack only contains Playwright internals
            if all('UtilityScript' in line or 'eval' in line for line in stack_lines):
                return True
                
        return False

    def _handle_console_msg(self, msg: ConsoleMessage):
        """Handle console messages and capture error details."""
        if msg.type == "error":
            message_text = msg.text
            
            # Check for our custom error format
            if message_text.startswith('CAPTURED_ERROR:'):
                try:
                    error_data = json.loads(message_text.replace('CAPTURED_ERROR:', '').strip())
                    
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
                        "user_agent": self._get_user_agent()
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
            
            location_data = {}
            if hasattr(msg, 'location') and msg.location:
                location_data = msg.location
            
            # Enhanced stack trace extraction
            stack_trace = ""
            try:
                # Try to get stack from console arguments
                for arg in msg.args:
                    try:
                        arg_value = arg.json_value()
                        if isinstance(arg_value, dict) and 'stack' in arg_value:
                            stack_trace = arg_value.get('stack', '')
                            break
                        elif isinstance(arg_value, str) and 'at ' in arg_value:
                            stack_trace = arg_value
                            break
                    except:
                        continue
                        
                # Extract location from message if available
                if not location_data and 'at https://' in message_text:
                    match = re.search(r'at\s+(https?://[^\s]+):(\d+):(\d+)', message_text)
                    if match:
                        location_data = {
                            'url': match.group(1),
                            'lineNumber': match.group(2),
                            'columnNumber': match.group(3)
                        }
                        if not stack_trace:
                            stack_trace = message_text
            except:
                pass
            
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
                "user_agent": self._get_user_agent()
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
            "stack_trace": getattr(error, 'stack', str(error)),
            "user_agent": self._get_user_agent()
        }
        
        self._store_error(error_info)
        print(f"  -> Page error stored for URL: {self.page.url}")

    def _store_error(self, error_info: Dict[str, Any]):
        """Store error information with the current URL as key."""
        current_url = self.page.url
        if current_url not in self.error_stacks:
            self.error_stacks[current_url] = []
        
        # Avoid duplicate errors
        for existing_error in self.error_stacks[current_url]:
            if (existing_error.get('message') == error_info.get('message') and 
                existing_error.get('stack_trace') == error_info.get('stack_trace')):
                return
                
        self.error_stacks[current_url].append(error_info)

    def _simulate_user_interaction(self, url: str):
        """Simulate user interactions based on error sources from RUM data."""
        print(f"Simulating user interactions for {url}...")
        try:
            url_errors = self.rum_errors.get(url, [])
            
            if not url_errors:
                print(f"  -> No specific RUM error sources for user interaction simulation on {url}.")
                return

            # Disable auto-waiting for navigation during simulations
            original_timeout = self.page.default_timeout
            self.page.set_default_timeout(3000)  # 3 second timeout for interactions

            for error in url_errors:
                error_source = error.get("error_source", "")
                print(f"  -> Simulating based on error source: {error_source}")
                
                try:
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
                except Exception as e:
                    print(f"    ! Error during simulation: {e}")
                    # Continue with other simulations even if one fails
                
                time.sleep(1)

            # Restore original timeout
            self.page.set_default_timeout(original_timeout)

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
                    
                # Only click the first visible button to avoid multiple navigations
                for element in elements[:1]:
                    if element.is_visible() and element.is_enabled():
                        print(f"    -> Clicking button: {selector}")
                        element.scroll_into_view_if_needed()
                        # Use no-wait click to avoid navigation issues
                        element.click(timeout=2000, no_wait_after=True)
                        time.sleep(1)
                        break
            except Exception as e:
                if "Execution context was destroyed" not in str(e):
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
                    time.sleep(0.5)
            except Exception as e:
                if "Execution context was destroyed" not in str(e):
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
                
            for form in forms[:1]:  # Only first form to avoid multiple submissions
                try:
                    # Find required inputs within this form and leave them empty
                    required_inputs = form.locator("[required]").all()
                    print(f"    -> Found {len(required_inputs)} required inputs in a form.")
                    
                    for input_elem in required_inputs:
                        try:
                            if input_elem.is_visible() and input_elem.is_editable():
                                print(f"      -> Clearing required input")
                                input_elem.fill("")
                        except:
                            continue
                    
                    # Try to submit the form with JavaScript to avoid navigation
                    try:
                        if form.is_visible() and form.is_enabled():
                            print("    -> Triggering form validation.")
                            # Use reportValidity instead of submit to avoid navigation
                            form.evaluate("form => form.reportValidity()")
                            time.sleep(1)
                    except:
                        pass
                            
                except Exception as e:
                    if "Execution context was destroyed" not in str(e):
                        print(f"  -> Failed to simulate form validation: {e}")
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
                    time.sleep(0.5)
            except Exception as e:
                if "Execution context was destroyed" not in str(e):
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
                                        close_button.click(timeout=2000, no_wait_after=True)
                                        break
                                except:
                                    continue
                        time.sleep(1)
                except Exception as e:
                    if "Execution context was destroyed" not in str(e):
                        print(f"  -> Failed to interact with modal/backdrop: {e}")
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

            # Navigate to the URL
            print(f"Navigating to {url}...")
            response = self.page.goto(url, wait_until="networkidle", timeout=60000)
            print(f"Page loaded with status: {response.status if response else 'N/A'}")

            # Cache user agent after navigation
            self.user_agent = self._safe_evaluate("navigator.userAgent", self.user_agent)

            # Wait for initial JavaScript execution
            time.sleep(2)

            # Retrieve any errors captured by our injected script
            try:
                captured_errors = self._safe_evaluate("window.__capturedErrors || []", [])
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
                            "user_agent": self._get_user_agent()
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
                final_errors = self._safe_evaluate("window.__capturedErrors || []", [])
                # Process any new errors that appeared during interaction
                # (similar to above but checking for new errors only)
            except:
                pass

        except Exception as e:
            print(f"Error analyzing {url}: {str(e)}")
            if "TimeoutError" not in str(e):
                error_info = {
                    "type": "navigation_error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                    "stack_trace": "",
                    "user_agent": self._get_user_agent()
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
        
        # Prepare data for the desired format
        formatted_error_traces = {}
        for url, errors in self.error_stacks.items():
            formatted_error_traces[url] = []
            for error_info in errors:
                # Only include errors with meaningful content
                if error_info.get("stack_trace") or 'TypeError' in error_info.get("message", '') or 'ReferenceError' in error_info.get("message", ''):
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
        
        # Print summary
        print(f"\nSummary:")
        print(f"- Total URLs processed: {len(self.rum_errors)}")
        print(f"- URLs with JavaScript errors: {len(formatted_error_traces)}")
        print(f"- Total JavaScript errors captured: {sum(len(errors) for errors in formatted_error_traces.values())}")

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