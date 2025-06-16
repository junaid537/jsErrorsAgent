# from dotenv import load_dotenv
# import os
# load_dotenv()
import json
import requests
# from browser_error_collector import BrowserErrorCollector
# from error_analysis_agents import ErrorAnalysisAgents
from datetime import datetime

def fetch_rum_data():
    """Fetch RUM data from Shred-It."""
    url = "https://bundles.aem.page/bundles/www.shredit.com/2025/04/10?domainkey=990874FF-082E-4910-97CE-87692D9E8C99-8E11F549&checkpoint=click"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching RUM data: {str(e)}")
        return None

def parse_rum_js_errors(rum_data):
    """Parse RUM data to extract JavaScript errors."""
    if not rum_data or 'rumBundles' not in rum_data:
        return {}

    rum_errors_by_url = {}

    for session in rum_data['rumBundles']:
        session_url = session.get("url")
        if not session_url:
            continue
        for event in session.get("events", []):
            if event.get("checkpoint") == "error":
                if session_url not in rum_errors_by_url:
                    rum_errors_by_url[session_url] = []

                error_info = {
                    "error_source": event.get("source"),
                    "user_agent": session.get("userAgent")
                }
                rum_errors_by_url[session_url].append(error_info)

    return rum_errors_by_url

def main():
    # browser_collector = BrowserErrorCollector()
    # error_agents = ErrorAnalysisAgents()
    try:
        rum_data = fetch_rum_data()

        if not rum_data:
            print("Failed to fetch RUM data")
            return
        
        rum_errors_by_url = parse_rum_js_errors(rum_data)

        # Print total count of errors
        total_errors = sum(len(errors) for errors in rum_errors_by_url.values())
        print(f"Found {total_errors} JavaScript error events from {len(rum_errors_by_url)} unique URLs.")

        # Save RUM errors to JSON file
        with open('rum_errors_by_url.json', 'w') as f:
            json.dump(rum_errors_by_url, f, indent=2)
        print("RUM errors saved to rum_errors_by_url.json")

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