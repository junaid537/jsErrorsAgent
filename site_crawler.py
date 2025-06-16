from playwright.sync_api import sync_playwright
import time
from urllib.parse import urljoin
import re

class SiteCrawler:
    def __init__(self, base_url):
        self.base_url = base_url
        self.visited_urls = set()
        self.console_errors = []
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self):
        """Initialize Playwright and browser."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        self.context = self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
        )
        self.page = self.context.new_page()

    def close(self):
        """Close browser and Playwright."""
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def is_valid_url(self, url):
        """Check if URL is valid and belongs to the same domain."""
        if not url:
            return False
        if url.startswith('javascript:'):
            return False
        if url.startswith('mailto:'):
            return False
        if url.startswith('tel:'):
            return False
        if not url.startswith(self.base_url):
            return False
        return True

    def collect_errors(self):
        """Collect console errors from the current page."""
        errors = self.page.evaluate("""() => {
            const errors = [];
            const originalConsoleError = console.error;
            console.error = (...args) => {
                errors.push(args.join(' '));
                originalConsoleError.apply(console, args);
            };
            return errors;
        }""")
        
        for error in errors:
            self.console_errors.append({
                'type': 'console_error',
                'text': error,
                'url': self.page.url,
                'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'collected_from': 'browser_console'
            })

    def collect_network_errors(self):
        """Collect failed network requests."""
        failed_requests = self.page.evaluate("""() => {
            return window.performance.getEntriesByType('resource')
                .filter(entry => entry.initiatorType !== 'xmlhttprequest' && entry.duration > 0)
                .map(entry => ({
                    url: entry.name,
                    duration: entry.duration,
                    initiatorType: entry.initiatorType
                }));
        }""")
        
        for request in failed_requests:
            if request['duration'] > 1000:  # Consider requests taking more than 1 second as potential issues
                self.console_errors.append({
                    'type': 'performance',
                    'text': f"Slow resource loading: {request['url']}",
                    'duration': request['duration'],
                    'initiatorType': request['initiatorType'],
                    'url': self.page.url,
                    'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S'),
                    'collected_from': 'browser_console'
                })

    def extract_links(self):
        """Extract all links from the current page."""
        links = self.page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(href => href && !href.startsWith('javascript:'));
        }""")
        return [link for link in links if self.is_valid_url(link)]

    def crawl_page(self, url):
        """Crawl a single page and collect errors."""
        if url in self.visited_urls:
            return
        
        print(f"Crawling: {url}")
        self.visited_urls.add(url)
        
        try:
            # Navigate to the page
            self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(2)  # Wait for dynamic content
            
            # Collect errors
            self.collect_errors()
            self.collect_network_errors()
            
            # Click all buttons and interactive elements
            self.page.evaluate("""() => {
                const clickableElements = document.querySelectorAll('button, [role="button"], [onclick]');
                clickableElements.forEach(el => {
                    try {
                        el.click();
                    } catch (e) {
                        console.error('Error clicking element:', e);
                    }
                });
            }""")
            
            time.sleep(1)  # Wait for click handlers
            
            # Collect errors after interactions
            self.collect_errors()
            self.collect_network_errors()
            
            # Extract and return links for further crawling
            return self.extract_links()
            
        except Exception as e:
            print(f"Error crawling {url}: {str(e)}")
            return []

    def crawl_site(self, max_pages=10):
        """Crawl the entire site starting from base_url."""
        self.start()
        try:
            urls_to_visit = [self.base_url]
            pages_visited = 0
            
            while urls_to_visit and pages_visited < max_pages:
                current_url = urls_to_visit.pop(0)
                new_links = self.crawl_page(current_url)
                
                if new_links:
                    urls_to_visit.extend([link for link in new_links if link not in self.visited_urls])
                
                pages_visited += 1
                print(f"Pages visited: {pages_visited}, URLs in queue: {len(urls_to_visit)}")
            
            return self.console_errors
            
        finally:
            self.close() 