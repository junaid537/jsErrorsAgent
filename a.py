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

'''






















































'''
Key Improvements in the Enhanced Version:
1. Error Filtering

Filters out CSP violations, network errors, and doubleclick.net errors
Only captures real JavaScript errors with meaningful stack traces
Configurable filtering options

2. Better Stack Trace Capture

Injects a script that overrides window.Error to capture stack traces immediately
Captures both error events and unhandled promise rejections
Extracts file names, line numbers, and column numbers from errors

3. Stack Trace Quality Checks

Removes Playwright internal frames from stack traces
Validates minimum stack depth
Avoids storing duplicate errors

4. Enhanced Error Information

Captures error type (console_error, page_error, uncaught_error, unhandled_rejection)
Includes location data (URL, line, column)
Preserves the original stack trace format

5. Summary Reporting

Generates a summary of captured errors
Shows most common error types and messages
Helps identify patterns in errors


'''

#from error_stack_collector.py