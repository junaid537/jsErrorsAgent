import json
from browser_error_collector import BrowserErrorCollector
from error_analysis_agents import ErrorAnalysisAgents
from typing import Dict, Any, List
import os
from dotenv import load_dotenv
import requests
from datetime import datetime

load_dotenv()

def fetch_rum_data(url: str) -> Dict[str, Any]:
    """Fetch RUM data from the provided URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching RUM data: {str(e)}")
        return None

def process_rum_bundles(rum_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process RUM bundles to extract relevant error information."""
    processed_errors = []
    
    if not rum_data or 'rumBundles' not in rum_data:
        return processed_errors
    
    for bundle in rum_data['rumBundles']:
        url = bundle.get('url')
        events = bundle.get('events', [])
        
        # Extract errors from events
        for event in events:
            if event.get('checkpoint') == 'error':
                error_info = {
                    'url': url,
                    'timestamp': bundle.get('time'),
                    'text': event.get('source', 'Unknown error'),
                    'target': event.get('target', ''),
                    'timeDelta': event.get('timeDelta', 0),
                    'userAgent': bundle.get('userAgent', '')
                }
                processed_errors.append(error_info)
    
    return processed_errors

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize components
    browser_collector = BrowserErrorCollector()
    error_agents = ErrorAnalysisAgents()
    
    try:
        # Fetch RUM data from URL
        rum_url = "https://bundles.aem.page/bundles/www.hersheyland.com/2025/04/10?domainkey=28ACC100-50CF-4FB4-87AE-C666E59403AA&checkpoint=click"
        rum_data = fetch_rum_data(rum_url)
        
        if not rum_data:
            raise ValueError("Failed to fetch RUM data")
        
        # Process RUM bundles to extract errors
        rum_errors = process_rum_bundles(rum_data)
        
        if not rum_errors:
            print("No errors found in RUM data")
            return
        
        # Get unique URLs from RUM errors
        urls_to_check = list(set(error['url'] for error in rum_errors))
        
        all_console_errors = []
        for url in urls_to_check:
            print(f"Checking URL: {url}")
            console_errors = browser_collector.collect_console_errors(url)
            all_console_errors.extend(console_errors)
        
        # Compare RUM errors with console errors
        comparison_result = browser_collector.compare_errors(rum_errors, all_console_errors)
        
        # Analyze new errors if any found
        if comparison_result['new_error_count'] > 0:
            print(f"Found {comparison_result['new_error_count']} new errors!")
            analysis_result = error_agents.analyze_errors(comparison_result['new_errors'])
            
            # Save analysis results with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f'error_analysis_results_{timestamp}.json'
            
            with open(output_file, 'w') as f:
                json.dump({
                    'rum_data_source': rum_url,
                    'analysis_time': timestamp,
                    'comparison': comparison_result,
                    'analysis': analysis_result
                }, f, indent=2)
            
            print(f"Analysis complete! Results saved to {output_file}")
        else:
            print("No new errors found!")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        browser_collector.close()

if __name__ == "__main__":
    main() 