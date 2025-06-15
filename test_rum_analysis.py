from dotenv import load_dotenv
import os
load_dotenv()
import json
import requests
from browser_error_collector import BrowserErrorCollector
from error_analysis_agents import ErrorAnalysisAgents
from datetime import datetime

def fetch_rum_data():
    """Fetch RUM data from Hersheyland."""
    url = "https://bundles.aem.page/bundles/www.hersheyland.com/2025/04/10?domainkey=28ACC100-50CF-4FB4-87AE-C666E59403AA&checkpoint=click"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching RUM data: {str(e)}")
        return None

def process_rum_bundles(rum_data):
    """Process RUM bundles to extract relevant information."""
    if not rum_data or 'rumBundles' not in rum_data:
        return []
    
    processed_data = []
    for bundle in rum_data['rumBundles']:
        bundle_info = {
            'url': bundle.get('url'),
            'timestamp': bundle.get('time'),
            'userAgent': bundle.get('userAgent'),
            'events': []
        }
        
        for event in bundle.get('events', []):
            if event.get('checkpoint') == 'error':
                bundle_info['events'].append({
                    'type': 'error',
                    'text': event.get('source', 'Unknown error'),
                    'target': event.get('target', ''),
                    'timeDelta': event.get('timeDelta', 0)
                })
            elif event.get('checkpoint') == 'loadresource':
                bundle_info['events'].append({
                    'type': 'resource',
                    'source': event.get('source', ''),
                    'target': event.get('target', ''),
                    'timeDelta': event.get('timeDelta', 0)
                })
        
        processed_data.append(bundle_info)
    
    return processed_data

def main():
    print("Starting RUM data analysis test...")
    
    # Initialize components
    browser_collector = BrowserErrorCollector()
    error_agents = ErrorAnalysisAgents()
    
    try:
        # Fetch RUM data
        print("Fetching RUM data...")
        rum_data = fetch_rum_data()
        
        if not rum_data:
            print("Failed to fetch RUM data")
            return
        
        # Process RUM bundles
        print("Processing RUM bundles...")
        processed_data = process_rum_bundles(rum_data)
        
        if not processed_data:
            print("No data found in RUM bundles")
            return
        
        print(f"Found {len(processed_data)} RUM bundles to analyze")
        
        # Analyze each unique URL
        urls_analyzed = set()
        all_console_errors = []
        
        for bundle in processed_data:
            url = bundle['url']
            if url not in urls_analyzed:
                print(f"\nAnalyzing URL: {url}")
                print(f"User Agent: {bundle['userAgent']}")
                
                # Collect console errors
                console_errors = browser_collector.collect_console_errors(url)
                all_console_errors.extend(console_errors)
                
                # Compare with RUM errors
                rum_errors = [event for event in bundle['events'] if event['type'] == 'error']
                comparison_result = browser_collector.compare_errors(rum_errors, console_errors)
                
                if comparison_result['new_error_count'] > 0:
                    print(f"\nFound {comparison_result['new_error_count']} new errors!")
                    
                    # Analyze new errors
                    analysis_result = error_agents.analyze_errors(comparison_result['new_errors'])
                    
                    # Save results
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_file = f'error_analysis_{url.split("/")[-1]}_{timestamp}.json'
                    
                    with open(output_file, 'w') as f:
                        json.dump({
                            'url': url,
                            'analysis_time': timestamp,
                            'comparison': comparison_result,
                            'analysis': analysis_result
                        }, f, indent=2)
                    
                    print(f"Analysis saved to {output_file}")
                else:
                    print("No new errors found for this URL")
                
                urls_analyzed.add(url)
        
        print("\nAnalysis complete!")
        
    except Exception as e:
        print(f"An error occurred during analysis: {str(e)}")
    finally:
        browser_collector.close()

if __name__ == "__main__":
    main() 