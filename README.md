# JavaScript Error Detection and Analysis System

This system uses CrewAI and Playwright to detect and analyze JavaScript errors from RUM (Real User Monitoring) data and browser console logs. It helps identify new errors, analyze their root causes, and provide solutions for fixing them.

## Features

- Collects JavaScript errors from browser console using Playwright
- Compares errors from RUM data with console errors
- Uses CrewAI agents to analyze errors and provide solutions
- Generates detailed reports with error analysis and fixes

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install
```

3. Create a `.env` file with any required API keys or configuration:
```bash
# Add your environment variables here
```

## Usage

1. Prepare your RUM data in JSON format and save it as `rum_data.json`. The file should contain:
   - URL of the page to analyze
   - List of errors from RUM data

2. Run the main script:
```bash
python main.py
```

3. The script will:
   - Load the RUM data
   - Open the page in a headless browser
   - Collect console errors
   - Compare with RUM errors
   - Analyze new errors using CrewAI agents
   - Save results to `error_analysis_results.json`

## Output

The system generates an `error_analysis_results.json` file containing:
- Comparison between RUM and console errors
- Detailed analysis of new errors
- Suggested fixes and improvements
- Performance optimization recommendations

## Notes

- The system focuses on non-minified code (EDS) for better error analysis
- It captures the full stack trace of errors
- The analysis includes timing information and user interaction context
- Results are saved in a structured JSON format for further processing 


Crew Ai will do these :
Have CrewAI analyze:
The root cause of each error
Potential fixes
Impact on user experience
Priority for fixing