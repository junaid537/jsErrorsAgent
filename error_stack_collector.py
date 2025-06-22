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