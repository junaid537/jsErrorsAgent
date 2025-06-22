# Multi-agent JavaScript Error Detection and Analysis

A comprehensive JavaScript error analysis pipeline using CrewAI agents to process Real User Monitoring (RUM) data and provide intelligent error analysis and code fixes.

## 🚀 Features

- **RUM Data Processing**: Fetches and processes Real User Monitoring data from web applications
- **Intelligent Error Analysis**: Uses AI agents to analyze JavaScript errors and provide root cause analysis
- **Code Fix Suggestions**: Generates specific fixes for JavaScript errors
- **Error Categorization**: Automatically categorizes errors (network, CSP violations, embed errors, etc.)
- **Filtering System**: Filters out minified files, malicious URLs, and errors without proper context
- **Batch Processing**: Processes errors individually or in batches with token limit management

## 📁 Project Structure

```
jsErrorsAgent/
├── main.py                              # Main pipeline orchestrator
├── test_iterate_single_error.py         # Individual error processing with CrewAI
├── test_single_error.py                 # Single error testing script
├── crewai_js_error_agents.py            # CrewAI agent definitions
├── parse_rum_js_errors.py               # RUM data parsing utilities
├── rum_errors_by_url_unique_description.json  # Processed error data
├── all_results.json                     # CrewAI analysis results
├── requirements.txt                     # Python dependencies
└── README.md                           # This file
```

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/junaid537/Multi-agent_Detect_JS-errors.git
   cd Multi-agent_Detect_JS-errors
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   Create a `.env` file in the root directory:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## 🔧 Usage

### Complete Pipeline (Recommended)

Run the complete pipeline that fetches RUM data, processes errors, and analyzes them with CrewAI:

```bash
python3 main.py
```

This will:
1. Fetch RUM data from the configured endpoint
2. Parse and filter JavaScript errors
3. Create `rum_errors_by_url_unique_description.json`
4. Automatically run CrewAI analysis on all errors
5. Generate `all_results.json` with analysis results

### Individual Error Processing

Process errors one by one with detailed analysis:

```bash
python3 test_iterate_single_error.py
```

### Single Error Testing

Test the system with a single error:

```bash
python3 test_single_error.py
```

## 🤖 CrewAI Agents

The system uses two specialized AI agents:

### 1. Expert JavaScript Error Analyzer
- **Role**: Senior Software Development Engineer
- **Purpose**: Analyzes error messages and code context to identify root causes
- **Output**: Detailed error analysis and fix suggestions

### 2. Expert JavaScript Fix Suggestor
- **Role**: Senior JavaScript Developer
- **Purpose**: Applies fixes based on the analyzer's suggestions
- **Output**: Corrected code with applied fixes

## 📊 Output Format

The `all_results.json` file contains structured analysis results:

```json
[
  {
    "error_description": "TypeError: Cannot read property 'x' of undefined",
    "error_snippet": "const value = obj.x;",
    "code_context": "function processData(obj) { const value = obj.x; return value; }",
    "agent1_response": "Root cause analysis and fix suggestions...",
    "agent2_response": "Fixed code with applied corrections..."
  }
]
```

## 🔍 Error Filtering

The system automatically filters out:

- **Minified files**: Files containing 'min' in the source
- **Embed sources**: Sources containing 'embed' in the URL
- **Malicious URLs**: URLs matching security patterns
- **Errors without line/column**: Errors lacking proper location information
- **Long context errors**: Errors with context > 1000 tokens

## 📈 Generated Files

- `rum_errors_by_url.json`: All parsed RUM errors
- `rum_errors_by_url_unique_description.json`: Deduplicated errors
- `errors_without_line_column.json`: Errors without proper location data
- `network_errors.json`: Network-related errors
- `csp_violation_errors.json`: Content Security Policy violations
- `minified_errors.json`: Errors from minified files
- `all_results.json`: Final CrewAI analysis results

## 🛡️ Security Features

- **URL Validation**: Filters malicious URLs using pattern matching
- **Safe URL Patterns**: Validates HTTP/HTTPS URLs only
- **Error Sanitization**: Cleans and validates error data before processing

## 🔧 Configuration

### RUM Data Source
Configure the RUM data endpoint in `main.py`:
```python
url = "https://bundles.aem.page/bundles/www.bulk.com/2025/04/10?domainkey=YOUR_KEY"
```

### CrewAI Settings
Modify agent parameters in `crewai_js_error_agents.py`:
- Model: `gpt-4o`
- Temperature: `0.5`
- Max iterations: `4`

## 📝 Dependencies

- `crewai`: Multi-agent orchestration
- `langchain-openai`: OpenAI integration
- `python-dotenv`: Environment variable management
- `requests`: HTTP requests for data fetching

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the existing issues
2. Create a new issue with detailed information
3. Include error logs and configuration details

## 🎯 Roadmap

- [ ] Add support for more error types
- [ ] Implement real-time error monitoring
- [ ] Add web interface for results visualization
- [ ] Support for multiple RUM data sources
- [ ] Enhanced error categorization
- [ ] Performance optimization for large datasets