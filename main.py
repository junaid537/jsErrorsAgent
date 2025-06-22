# from dotenv import load_dotenv
# import os
# load_dotenv()
import json
import requests
import re
from urllib.parse import urlparse
# from browser_error_collector import BrowserErrorCollector
# from error_analysis_agents import ErrorAnalysisAgents
from datetime import datetime
# from error_stack_collector import run_diagnostic_collection
import os

# Define patterns that indicate malicious content
MALICIOUS_PATTERNS = [
    r"sleep\((\d+|\d+\*\d+)\)",
    r"waitfor\s+delay",
    r"select\s+\d+\s+from\s+pg_sleep",
    r"xor\s*\(",
    r"['\"%27%22][^ ]*['\"%27%22]",
    r"concat\(",
    r"(require|socket|gethostbyname)",
    r"(win\.ini|etc/passwd)",
    r"<script>|esi:include",
    r"dbms_pipe\.receive_message",
]

# Compile regex patterns
compiled_patterns = [re.compile(p, re.IGNORECASE) for p in MALICIOUS_PATTERNS]

def is_safe_url(url: str) -> bool:
    """Filters out URLs that match known malicious patterns or are not proper HTTP/HTTPS URLs."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
    except:
        return False

    # Check for known malicious patterns
    for pattern in compiled_patterns:
        if pattern.search(url):
            return False

    return True

def fetch_rum_data():
    """Fetch RUM data from Shred-It."""
    #url = "https://bundles.aem.page/bundles/www.bulk.com/2025/04/10?domainkey=8C96BCA5-AAA9-4C2F-83AA-25D98ED91F8A-8E11F549&checkpoint=click"
    url = "https://bundles.aem.page/bundles/www.wilson.com/2025/04/10?domainkey=B6A7571C-1066-48BD-911A-A22B5941DAD2-8E11F549&checkpoint=click"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching RUM data: {str(e)}")
        return None

def get_error_part_in_code(code_link, line, column, context_radius=20):
    if not code_link or line is None or column is None:
        return None
    try:
        response = requests.get(code_link, timeout=10)
        if response.status_code != 200:
            return f"⚠️ Failed to fetch JS file: HTTP {response.status_code}"
        js_lines = response.text.splitlines()
        # Convert to 0-based index
        line_index = line - 1
        if line_index < 0 or line_index >= len(js_lines):
            return "Line number out of bounds!"
        target_line = js_lines[line_index]
        line_length = len(target_line)
        if column < 0 or column >= line_length:
            return "Column number out of bounds!"
        start = max(0, column - context_radius)
        end = min(line_length, column + context_radius + 1)
        snippet = target_line[start:end]
        return snippet
    except Exception as e:
        return f"❌ Exception: {str(e)}"

def get_code_context_and_max_tokens(code_link, line, context_radius=30):
    """Fetch 30 lines before and after the error line, return context and max words in any line."""
    if not code_link or line is None:
        return None, None
    try:
        response = requests.get(code_link, timeout=10)
        if response.status_code != 200:
            return f"⚠️ Failed to fetch JS file: HTTP {response.status_code}", None
        js_lines = response.text.splitlines()
        line_index = line - 1
        start = max(0, line_index - context_radius)
        end = min(len(js_lines), line_index + context_radius + 1)
        context_lines = js_lines[start:end]
        context_code = "\n".join(context_lines)
        max_tokens = max((len(l.split()) for l in context_lines), default=0)
        return context_code, max_tokens
    except Exception as e:
        return f"❌ Exception: {str(e)}", None

def parse_rum_js_errors(rum_data):
    """Parse RUM data to extract JavaScript errors."""
    if not rum_data or 'rumBundles' not in rum_data:
        return {}, {}, {}, {}, {}

    rum_errors_by_url = {}
    minified_errors = {}
    embed_errors = {}
    network_errors = {}
    csp_violation_errors = {}

    for session in rum_data['rumBundles']:
        session_url = session.get("url")
        if not session_url:
            continue

        for event in session.get("events", []):
            if event.get("checkpoint") == "error":
                # Filter out malicious URLs at this stage
                if not is_safe_url(session_url):
                    print(f"Skipping malicious URL: {session_url}")
                    continue

                error_source = event.get("source", "")
                # Skip errors from minified files
                if 'min' in error_source.lower():
                    continue

                if session_url not in rum_errors_by_url:
                    rum_errors_by_url[session_url] = []

                error_description = event.get("target", None)
                code_link = None
                line = None
                column = None
                match = re.search(r'(https?://[^\s:]+\.js)(?::(\d+))?(?::(\d+))?', error_source)
                if match:
                    code_link = match.group(1)
                    if match.group(2):
                        line = int(match.group(2))
                    if match.group(3):
                        column = int(match.group(3))
                error_part_in_code = get_error_part_in_code(code_link, line, column)
                context_code, max_tokens = get_code_context_and_max_tokens(code_link, line)
                error_info = {
                    "error_source": error_source,
                    "user_agent": session.get("userAgent"),
                    "code_link": code_link,
                    "line": line,
                    "column": column,
                    "error_description": error_description,
                    "error_part_in_code": error_part_in_code,
                    "context_code": context_code,
                    "max_tokens_length_in_code_context": max_tokens
                }
                rum_errors_by_url[session_url].append(error_info)

    return rum_errors_by_url, minified_errors, embed_errors, network_errors, csp_violation_errors

def split_errors_by_line_column(rum_errors_by_url):
    errors_with_line_col = {}
    errors_without_line_col = {}
    for url, errors in rum_errors_by_url.items():
        with_line_col = []
        without_line_col = []
        for err in errors:
            if err.get("line") is not None and err.get("column") is not None:
                with_line_col.append(err)
            else:
                without_line_col.append(err)
        if with_line_col:
            errors_with_line_col[url] = with_line_col
        if without_line_col:
            errors_without_line_col[url] = without_line_col
    return errors_with_line_col, errors_without_line_col

def keep_unique_error_descriptions(rum_errors_by_url):
    unique_by_desc = {}
    for url, errors in rum_errors_by_url.items():
        seen = set()
        unique_errors = []
        for err in errors:
            desc = err.get("error_description")
            desc_norm = desc.strip().lower() if isinstance(desc, str) else desc
            if desc_norm not in seen:
                seen.add(desc_norm)
                unique_errors.append(err)
        if unique_errors:
            unique_by_desc[url] = unique_errors
    return unique_by_desc

def main():
    # browser_collector = BrowserErrorCollector()
    # error_agents = ErrorAnalysisAgents()
    try:
        rum_data = fetch_rum_data()

        if not rum_data:
            print("Failed to fetch RUM data")
            return
        
        rum_errors_by_url, minified_errors, embed_errors, network_errors, csp_violation_errors = parse_rum_js_errors(rum_data)

        # Split errors by presence of line/column
        rum_errors_by_url, errors_without_line_col = split_errors_by_line_column(rum_errors_by_url)

        # Merge embed errors with errors without line/column
        for url, embed_error_list in embed_errors.items():
            if url in errors_without_line_col:
                errors_without_line_col[url].extend(embed_error_list)
            else:
                errors_without_line_col[url] = embed_error_list

        # Print total count of errors
        total_errors = sum(len(errors) for errors in rum_errors_by_url.values())
        total_embed_errors = sum(len(errors) for errors in embed_errors.values())
        total_network_errors = sum(len(errors) for errors in network_errors.values())
        total_csp_errors = sum(len(errors) for errors in csp_violation_errors.values())
        print(f"Found {total_errors} JavaScript error events from {len(rum_errors_by_url)} unique URLs (after filtering malicious ones).")
        print(f"Found {total_embed_errors} embed error events from {len(embed_errors)} unique URLs.")
        print(f"Found {total_network_errors} network error events from {len(network_errors)} unique URLs.")
        print(f"Found {total_csp_errors} CSP violation error events from {len(csp_violation_errors)} unique URLs.")

        # Save RUM errors to JSON file
        with open('rum_errors_by_url.json', 'w') as f:
            json.dump(rum_errors_by_url, f, indent=2)
        print("RUM errors saved to rum_errors_by_url.json")

        # Save errors without line/column to a separate file
        with open('errors_without_line_column.json', 'w') as f:
            json.dump(errors_without_line_col, f, indent=2)
        print("Errors without line/column saved to errors_without_line_column.json")

        # Save network errors separately
        if network_errors:
            with open('network_errors.json', 'w') as f:
                json.dump(network_errors, f, indent=2)
            print("Network errors saved to network_errors.json")

        # Save CSP violation errors separately
        if csp_violation_errors:
            with open('csp_violation_errors.json', 'w') as f:
                json.dump(csp_violation_errors, f, indent=2)
            print("CSP violation errors saved to csp_violation_errors.json")

        # Save minified errors separately
        if minified_errors:
            with open('minified_errors.json', 'w') as f:
                json.dump(minified_errors, f, indent=2)
            print("Minified errors saved to minified_errors.json")

        # Save unique error_description per URL
        rum_errors_by_url_unique_description = keep_unique_error_descriptions(rum_errors_by_url)
        with open('rum_errors_by_url_unique_description.json', 'w') as f:
            json.dump(rum_errors_by_url_unique_description, f, indent=2)
        print("RUM errors with unique error_description per URL saved to rum_errors_by_url_unique_description.json")

        # Call CrewAI processing script
        print("\nStarting CrewAI error analysis and processing...")
        os.system("python3 test_iterate_single_error.py")
        print("CrewAI processing completed!")

        # Collect error stacks using Playwright
        # print("\nCollecting error stacks using Playwright...")
        # error_stacks = run_diagnostic_collection()
        # Print summary of collected error stacks
        # total_stacks = sum(len(stacks) for stacks in error_stacks.values())
        # print(f"\nCollected {total_stacks} error stacks across {len(error_stacks)} URLs")

        # Deminify errors using source maps
        # print("\nDeminifying errors using source maps...")
        # from deminify_errors import run_deminification
        # run_deminification()
        # print("Deminification complete. See deminified_errors.json.")

        # CrewAI error analysis and code fix
        # print("\nStarting CrewAI error analysis...")
        # error_agents.process_errors_in_batches("rum_errors_by_url.json", batch_size=2)
        # print("CrewAI analysis complete!")

        # # Example of how to use it (commented out)
        # for url, errors in rum_errors_by_url.items():
        #     print(f"\nAnalyzing URL: {url}")
        #     # console_errors = browser_collector.collect_console_errors(url)
        #     # print(f"Collected {len(console_errors)} console errors for {url}")
        #
        #     # # Compare and analyze errors (commented out)
        #     # if rum_errors and console_errors:
        #     #     comparison_results = browser_collector.compare_errors(errors, console_errors)
        #     #     print("Comparison Results:", comparison_results)
        #     #
        #     #     # If there are new errors, send to CrewAI for analysis (commented out)
        #     #     if comparison_results['new_error_count'] > 0:
        #     #         print("Sending new errors to CrewAI for analysis...")
        #     #         crew_analysis_results = analysis_agents.analyze_errors(comparison_results['new_errors'])
        #     #         print("CrewAI Analysis Results:", crew_analysis_results)
        #     # else:
        #     #     print("No errors to compare or analyze.")

    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
    # finally:
    #     # Ensure browser is closed even if errors occur (commented out)
    #     # if 'browser_collector' in locals() and browser_collector.browser:
    #     #     browser_collector.close()

if __name__ == "__main__":
    main()
'''
    # --- CrewAI Agent Integration ---
    try:
        print("\nStarting CrewAI agent-based error analysis...\n")
        from crewai_js_error_agents import JavaScriptErrorAnalysisSystem
        js_error_system = JavaScriptErrorAnalysisSystem()
        results = js_error_system.process_json_data('rum_errors_by_url_unique_description.json')
        print("\nCrewAI batch analysis completed!\n")
        for res in results:
            print(f"Chunk {res['chunk_id']} ({res['json_objects_count']} errors, {res['token_count']} tokens):")
            print(res['analysis_result'])
            print("-"*60)
    except Exception as e:
        print(f"CrewAI agent pipeline failed: {e}") '''