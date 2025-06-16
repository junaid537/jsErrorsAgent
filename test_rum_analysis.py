from dotenv import load_dotenv
import os
load_dotenv()
import json
import requests
from playwright.sync_api import sync_playwright
import time
from error_analysis_agents import ErrorAnalysisAgents
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

def collect_network_errors(page):
    """Collect failed network requests."""
    return page.evaluate("""() => {
        return window.performance.getEntriesByType('resource')
            .filter(entry => entry.initiatorType !== 'xmlhttprequest' && entry.duration > 0)
            .map(entry => ({
                url: entry.name,
                duration: entry.duration,
                initiatorType: entry.initiatorType
            }));
    }""")

def crawl_page(page, url, visited_urls, all_errors):
    """Crawl a single page and collect errors."""
    if url in visited_urls:
        return []
    
    print(f"Crawling: {url}")
    visited_urls.add(url)
    
    try:
        # Navigate to the page
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        time.sleep(2)  # Wait for dynamic content
        
        # Collect network errors (slow resources)
        network_requests = collect_network_errors(page)
        for request in network_requests:
            if request['duration'] > 1000:  # Consider requests taking more than 1 second as potential issues
                all_errors.append({
                    'type': 'performance',
                    'text': f"Slow resource loading: {request['url']}",
                    'duration': request['duration'],
                    'initiatorType': request['initiatorType'],
                    'url': page.url,
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'collected_from': 'browser_console'
                })
        
        # Click all buttons and interactive elements
        page.evaluate("""() => {
            const clickableElements = document.querySelectorAll('button, [role=\"button\"], [onclick]');
            clickableElements.forEach(el => {
                try {
                    el.click();
                } catch (e) {
                    console.error('Error clicking element:', e);
                }
            });
        }""")
        
        time.sleep(1)  # Wait for click handlers
        
        # Extract links for further crawling
        links = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(href => href && !href.startsWith('javascript:'));
        }""")
        
        return [link for link in links if link.startswith('https://www.shredit.com/en-us')]
        
    except Exception as e:
        print(f"Error crawling {url}: {str(e)}")
        return []

def main():
    print("Starting comprehensive RUM and site analysis...")
    
    # Initialize components
    error_agents = ErrorAnalysisAgents()
    visited_urls = set()
    all_errors = []
    
    # Start Playwright
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)  # Run in headful mode
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        # --- Real-time console event listener (all types) ---
        def handle_console_msg(msg):
            print(f"[Console {msg.type}] {msg.text} @ {page.url}")
            all_errors.append({
                "type": f"console_{msg.type}",
                "text": msg.text,
                "location": msg.location,
                "url": page.url,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
                "collected_from": "browser_console"
            })
        page.on("console", handle_console_msg)
        # ---------------------------------------------------

        # --- Network request failure event listener ---
        def handle_request_failed(request):
            print(f"[Network Error] {request.url} - {request.failure.error_text} @ {page.url}")
            all_errors.append({
                "type": "network_error",
                "text": request.failure.error_text,
                "url": request.url,
                "page_url": page.url,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
                "collected_from": "network"
            })
        page.on("requestfailed", handle_request_failed)
        # ---------------------------------------------
        
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
            
            # Start crawling from base URL
            print("\nStarting comprehensive site crawling...")
            urls_to_visit = ["https://www.shredit.com/en-us"]
            pages_visited = 0
            
            while urls_to_visit and pages_visited < 20:  # Crawl up to 20 pages
                current_url = urls_to_visit.pop(0)
                new_links = crawl_page(page, current_url, visited_urls, all_errors)
                
                if new_links:
                    urls_to_visit.extend([link for link in new_links if link not in visited_urls])
                
                pages_visited += 1
                print(f"Pages visited: {pages_visited}, URLs in queue: {len(urls_to_visit)}")
            
            # Print all collected errors after crawling
            print("\n--- All Errors Collected from 20 Pages ---")
            if all_errors:
                for err in all_errors:
                    if err['type'].startswith('console_'):
                        print(f"[Console] URL: {err['url']} | Type: {err['type']} | Error: {err['text']} | Location: {err['location']}")
                    elif err['type'] == 'network_error':
                        print(f"[Network] Page: {err['page_url']} | Resource: {err['url']} | Error: {err['text']}")
                    elif err['type'] == 'performance':
                        print(f"[Performance] URL: {err['url']} | {err['text']} | Duration: {err['duration']}ms")
            else:
                print("No errors detected on any of the 20 crawled pages.")
            print("--- End of All Errors ---\n")

            # Analyze each unique URL from RUM data
            urls_analyzed = set()
            
            for bundle in processed_data:
                url = bundle['url']
                if url not in urls_analyzed:
                    print(f"\nAnalyzing URL: {url}")
                    print(f"User Agent: {bundle['userAgent']}")
                    
                    # Get RUM errors for this URL
                    rum_errors = [event for event in bundle['events'] if event['type'] == 'error']
                    
                    # Get all errors for this URL
                    url_errors = [error for error in all_errors if (error.get('url') == url or error.get('page_url') == url)]
                    
                    if url_errors:
                        print(f"Found {len(url_errors)} errors for this URL")
                        
                        # Analyze errors
                        analysis_result = error_agents.analyze_errors(url_errors)
                        
                        # Save results
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_file = f'error_analysis_{url.split("/")[-1]}_{timestamp}.json'
                        
                        with open(output_file, 'w') as f:
                            json.dump({
                                'url': url,
                                'analysis_time': timestamp,
                                'errors': url_errors,
                                'analysis': str(analysis_result),  # Convert to string for JSON
                                'crawled_pages': list(visited_urls)
                            }, f, indent=2)
                        
                        print(f"Analysis saved to {output_file}")
                    else:
                        print("No errors found for this URL")
                    
                    urls_analyzed.add(url)
            
            print("\nAnalysis complete!")
            print(f"Total pages crawled: {len(visited_urls)}")
            print(f"Total errors collected: {len(all_errors)}")
            
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    main() 