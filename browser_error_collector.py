# This file previously contained the BrowserErrorCollector class and related Playwright code.
# Its contents have been commented out as per your request to disable Playwright functionality.
# You can uncomment this code or restore the file content if you wish to re-enable Playwright.

# import time
# from playwright.sync_api import sync_playwright
# import json

# class BrowserErrorCollector:
#     def __init__(self):
#         self.browser = None
#         self.context = None
#         self.page = None
#         self.console_errors = []
#         self.network_failures = []

#     def start_browser(self, headless=True):
#         self.playwright = sync_playwright().start()
#         self.browser = self.playwright.chromium.launch(headless=headless)
#         self.context = self.browser.new_context(
#             viewport={'width': 1280, 'height': 720},
#             user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
#         )
#         self.page = self.context.new_page()

#         # Listen for console messages
#         self.page.on("console", self._handle_console_msg)
#         # Listen for page errors (uncaught exceptions)
#         self.page.on("pageerror", self._handle_page_error)
#         # Listen for failed network requests
#         self.page.on("requestfailed", self._handle_failed_request)

#     def _handle_console_msg(self, msg):
#         if msg.type == "error":
#             self.console_errors.append({
#                 "type": "console_error",
#                 "text": msg.text,
#                 "location": msg.location,
#                 "url": self.page.url,
#                 "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
#                 "collected_from": "browser_console"
#             })
#         elif msg.type == "warning":
#             # You can choose to collect warnings as well
#             pass
#         # You can add logic for 'log', 'info', 'debug' etc.

#     def _handle_page_error(self, error):
#         self.console_errors.append({
#             "type": "page_error",
#             "text": str(error),
#             "url": self.page.url,
#             "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
#             "collected_from": "page_error"
#         })

#     def _handle_failed_request(self, request):
#         self.network_failures.append({
#             "type": "network_failure",
#             "url": request.url,
#             "method": request.method,
#             "failure_text": request.failure.error_text,
#             "status": None, # We can't reliably get the status for failed requests
#             "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
#             "collected_from": "network_request"
#         })

#     def collect_console_errors(self, url):
#         """Collect JavaScript errors from the browser console for a given URL."""
#         self.console_errors = []  # Clear previous errors for new URL
#         self.network_failures = [] # Clear previous network failures

#         if not self.page:
#             self.start_browser(headless=False) # Launch in headful mode for better visibility

#         print(f"Navigating to {url} in headless browser...")
#         try:
#             response = self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
#             print(f"Page loaded with status: {response.status if response else 'N/A'}")
#             time.sleep(10) # Give page time to load and execute JS
#         except Exception as e:
#             print(f"Error navigating to {url}: {e}")

#         # After navigation, capture any additional console errors or network failures
#         # The event listeners handle real-time capture, so we just return the collected ones
#         all_collected_errors = []
#         all_collected_errors.extend(self.console_errors)
#         all_collected_errors.extend(self.network_failures)
#         return all_collected_errors

#     def compare_errors(self, rum_errors, console_errors):
#         """Compares RUM errors with console errors to identify new issues."""
#         new_errors = []
#         rum_error_set = set(e['text'] for e in rum_errors)

#         for console_err in console_errors:
#             if console_err['text'] not in rum_error_set:
#                 new_errors.append(console_err)
#         
#         return {
#             "total_rum_errors": len(rum_errors),
#             "total_console_errors": len(console_errors),
#             "new_error_count": len(new_errors),
#             "new_errors": new_errors
#         }

#     def close(self):
#         """Closes the browser instance."""
#         if self.browser:
#             self.browser.close()
#         if self.playwright:
#             self.playwright.stop() 