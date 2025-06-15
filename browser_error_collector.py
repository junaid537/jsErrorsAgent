from playwright.sync_api import sync_playwright, Page, ConsoleMessage
import json
from typing import List, Dict, Any
import time
from datetime import datetime
import traceback

class BrowserErrorCollector:
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.errors = []
        
        # Enable more detailed console logging
        self.page.on("console", self._handle_console)
        self.page.on("pageerror", self._handle_page_error)
        self.page.on("requestfailed", self._handle_failed_request)

    def collect_console_errors(self, url: str) -> List[Dict[str, Any]]:
        """Collect JavaScript errors from the browser console."""
        self.errors = []
        
        try:
            print(f"Navigating to {url} in headless browser...")
            # Navigate to the URL with a more lenient wait strategy
            response = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            if not response:
                print(f"Failed to load {url}")
                return self.errors
                
            print(f"Page loaded with status: {response.status}")
            
            # Wait for potential errors and JavaScript execution
            time.sleep(10)  # Increased wait time
            
            # Execute JavaScript to get more detailed error information
            js_errors = self.page.evaluate("""() => {
                const errors = [];
                if (window.performance && window.performance.getEntriesByType) {
                    const resources = window.performance.getEntriesByType('resource');
                    resources.forEach(resource => {
                        if (resource.duration > 1000) { // Resources taking more than 1 second
                            errors.push({
                                type: 'performance',
                                text: `Slow resource loading: ${resource.name}`,
                                duration: resource.duration,
                                initiatorType: resource.initiatorType
                            });
                        }
                    });
                }
                return errors;
            }""")
            
            # Add performance errors to our collection
            for error in js_errors:
                error.update({
                    'url': url,
                    'timestamp': datetime.now().isoformat(),
                    'collected_from': 'performance_metrics'
                })
                self.errors.append(error)
            
            # Add additional context to all errors
            for error in self.errors:
                error.update({
                    'url': url,
                    'timestamp': datetime.now().isoformat(),
                    'collected_from': 'browser_console',
                    'user_agent': self.page.evaluate('navigator.userAgent'),
                    'viewport': self.page.viewport_size
                })
            
            return self.errors
            
        except Exception as e:
            print(f"Error collecting console errors for {url}: {str(e)}")
            print(f"Stack trace: {traceback.format_exc()}")
            return []

    def _handle_console(self, msg: ConsoleMessage):
        """Handle console messages and collect errors."""
        if msg.type == "error":
            try:
                # Get detailed error information
                error_info = {
                    'type': 'error',
                    'text': msg.text,
                    'stack': msg.stack if hasattr(msg, 'stack') else None,
                    'source': msg.location.get('url') if hasattr(msg, 'location') else None,
                    'line': msg.location.get('lineNumber') if hasattr(msg, 'location') else None,
                    'column': msg.location.get('columnNumber') if hasattr(msg, 'location') else None,
                    'timestamp': datetime.now().isoformat()
                }
                
                # If we have a stack trace, try to get more context
                if error_info['stack']:
                    # Extract the relevant part of the stack trace
                    stack_lines = error_info['stack'].split('\n')
                    error_info['stack_trace'] = [
                        {
                            'function': line.strip().split('at ')[-1] if 'at ' in line else line.strip(),
                            'line': line
                        }
                        for line in stack_lines if line.strip()
                    ]
                
                self.errors.append(error_info)
                print(f"Captured error: {error_info['text']}")
                
            except Exception as e:
                print(f"Error processing console message: {str(e)}")

    def _handle_page_error(self, error):
        """Handle uncaught page errors."""
        error_info = {
            'type': 'page_error',
            'text': str(error),
            'timestamp': datetime.now().isoformat()
        }
        self.errors.append(error_info)
        print(f"Captured page error: {error}")

    def _handle_failed_request(self, request):
        """Handle failed network requests."""
        error_info = {
            'type': 'network_error',
            'text': f"Failed request: {request.url}",
            'status': None,  # We can't reliably get the status for failed requests
            'timestamp': datetime.now().isoformat()
        }
        self.errors.append(error_info)
        print(f"Captured failed request: {request.url}")

    def compare_errors(self, rum_errors: List[Dict[str, Any]], console_errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare RUM errors with console errors to find new issues."""
        # Create a set of error signatures from RUM data
        rum_error_signatures = set()
        for error in rum_errors:
            # Create a unique signature based on error text and URL
            signature = f"{error.get('text', '')}:{error.get('url', '')}"
            rum_error_signatures.add(signature)
        
        # Find new errors
        new_errors = []
        for error in console_errors:
            signature = f"{error.get('text', '')}:{error.get('url', '')}"
            if signature not in rum_error_signatures:
                new_errors.append(error)
        
        return {
            'new_errors': new_errors,
            'total_rum_errors': len(rum_errors),
            'total_console_errors': len(console_errors),
            'new_error_count': len(new_errors),
            'rum_error_details': rum_errors,
            'console_error_details': console_errors
        }

    def close(self):
        """Clean up browser resources."""
        self.context.close()
        self.browser.close()
        self.playwright.stop() 