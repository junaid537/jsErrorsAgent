import os
from dotenv import load_dotenv
load_dotenv()
import json
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
import hashlib

def hash_url(url):
    return hashlib.md5(url.encode('utf-8')).hexdigest()

class JavascriptErrorAgents:
    def __init__(self, openai_api_key: str):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.5)
    
    def expert_Javascript_error_analyzer(self):
        return Agent(
            role="Expert JavaScript Error Analyzer and Senior Software Development Engineer",
            goal="Given the error message and the relevant code context/ code snippet, provide detailed root cause analysis on that error",
            backstory="You are a highly experienced JavaScript debugging specialist who analyzes real code errors.",
            llm=self.llm,
            tools=[],
            verbose=True,
            memory=False,
            allow_delegation=False,
            max_iter=4
        )

    def expert_Javascript_fix_suggestor(self):
        return Agent(
            role="Expert JavaScript Debugger and Senior Javascript Developer",
            goal="Apply specific fixes to JavaScript code based on error analysis given by expert_Javascript_error_analyzer and return the new fixed code",
            backstory="You are a senior frontend engineer who fixes real JavaScript bugs.",
            llm=self.llm,
            tools=[],
            verbose=True,
            memory=False,
            allow_delegation=False,
            max_iter=4
        )
    def analyze_errors_task(self, input_json):
        return Task(
            description=(
                f"You are given this specific JavaScript error message: {input_json[list(input_json.keys())[0]]['error_description']} and specific error line from the code:\n{input_json[list(input_json.keys())[0]]['error_snippet']}\n\n"
                f"The relevant code context holding that error is:\n{input_json[list(input_json.keys())[0]]['code_context']}\n\n"
                "You are also given code_context around the error_snippet! The entire code context might not be syntactically absolutely right or complete, as few lines are fetched around the error snippet so as not to breach input token limit of LLM! "
                "First locate the error line inside the context code provided to you then match the actual error description provided above. For the error:\n"
                "1. Locate the error snippet in the code context.\n"
                "2. Explain the root cause of this specific error.\n"
                "3. Suggest steps to fix the error in the code!!!!!\n\n"
                
                "Return the suggestion:\n"
                "[\n"
                "  {\n"
                f"   'error': '{list(input_json.keys())[0]}',\n"
                "    'issue': '<specific root cause for this error>',\n"
                "    'suggestion': '<specific fix for this code>'\n"
                "    'Steps to fix the code': '<Bullet points to fix the error>'\n"
                "  }\n"
                "]"
            ),
            agent=self.expert_Javascript_error_analyzer(),
            expected_output="List with one best suggestion for the specific error",
            input=input_json
        )

    def fix_errors_task(self, original_errors_json, analyzer_output):
        return Task(
            description=(
                f"You are given this specific JavaScript error message: {original_errors_json[list(original_errors_json.keys())[0]]['error_description']} and specific error line from the code:\n{original_errors_json[list(original_errors_json.keys())[0]]['error_snippet']}\n\n"
                f"IMPORTANT: You will receive the analysis from the Expert JavaScript Error Analyzer in the context from the previous task. Use his suggestions to fix that specific error in the code context and return bug free code context.\n\n"
                f"The relevant code context holding that error is:\n{original_errors_json[list(original_errors_json.keys())[0]]['code_context']}\n\n"
                "Just Return the updated code block after applying the fixes suggested by the Expert JavaScript Error Analyzer.\n\n"
                "Output format:\n"
                "[\n"
                "  {\n"
                #f"    'error': '{list(original_errors_json.keys())[0]}',\n"
                "    'fixed_code': '<the corrected code for this specific error>'\n"
                "  }\n"
                "]"
            ),
            agent=self.expert_Javascript_fix_suggestor(),
            expected_output="Fixed JavaScript code for the specific error using the suggestion from Expert JavaScript Debugger and Senior Javascript Developer",
            input=original_errors_json,
            context=[analyzer_output]
        )
    '''def analyze_errors_task(self, input_json):
        return Task(
            description=(
                f"You are given this specific JavaScript error message: {input_json[list(input_json.keys())[0]].get('error_description', '')} and specific error line from the code:\n{input_json[list(input_json.keys())[0]].get('error_snippet', '')}\n\n"
                f"The relevant code context holding that error is:\n{input_json[list(input_json.keys())[0]].get('code_context', '')}\n\n"
                "You are also given code_context around the error_snippet! The entire code context might not be syntactically absolutely right or complete, as few lines are fetched around the error snippet so as not to breach input token limit of LLM! "
                "First locate the error snippet inside the code provided to you then analyze the actual error provided above. For the error:\n"
                "1. Locate the error snippet in the code context.\n"
                "2. Explain the root cause of this specific error.\n"
                "3. Suggest a suggestion to fix for this specific code.\n\n"
                "Return the suggestion:\n"
                "[\n"
                "  {\n"
                f"   'error': '{list(input_json.keys())[0]}',\n"
                "    'issue': '<specific root cause for this error>',\n"
                "    'suggestion': '<specific fix for this code>'\n"
                "  }\n"
                "]"
            ),
            agent=self.expert_Javascript_error_analyzer(),
            expected_output="List with one best suggestion for the specific error",
            input=input_json
        )

    def fix_errors_task(self, original_errors_json, analyzer_output):
        return Task(
            description=(
                f"You are given this specific JavaScript error message: {original_errors_json[list(original_errors_json.keys())[0]].get('error_description', '')} and specific error line from the code:\n{original_errors_json[list(original_errors_json.keys())[0]].get('error_snippet', '')}\n\n"
                f"IMPORTANT: You will receive the analysis from the Expert JavaScript Error Analyzer in the context from the previous task. Use that analysis to understand the root cause and apply the specific suggestion to fix the code.\n\n"
                f"The relevant code context holding that error is:\n{original_errors_json[list(original_errors_json.keys())[0]].get('code_context', '')}\n\n"
                "Return the updated code block as bug-free JavaScript.\n\n"
                "Output format:\n"
                "[\n"
                "  {\n"
                "    'fixed_code': '<the corrected code for this specific error>'\n"
                "  }\n"
                "]"
            ),
            agent=self.expert_Javascript_fix_suggestor(),
            expected_output="Fixed JavaScript code for the specific error using the suggestion from Expert JavaScript Debugger and Senior Javascript Developer",
            input=original_errors_json,
            context=[analyzer_output]
        )'''

if __name__ == "__main__":
    OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
    agents = JavascriptErrorAgents(OPENAI_API_KEY)

    # Load the RUM errors JSON
    with open("rum_errors_by_url_unique_description.json", "r", encoding="utf-8") as f:
        rum_errors_by_url = json.load(f)

    all_results = []
    processed_count = 0
    skipped_count = 0
    total_errors = sum(len(errors) for errors in rum_errors_by_url.values())
    
    print(f"Total errors to process: {total_errors}")

    # Iterate over every error in every URL
    for url, errors in rum_errors_by_url.items():
        for idx, error in enumerate(errors):
            # Filter out errors without line/column numbers or with too long context
            line = error.get('line')
            column = error.get('column')
            max_tokens = error.get('max_tokens_length_in_code_context', 0)
            
            # Skip errors without line/column numbers
            if line is None or column is None:
                skipped_count += 1
                print(f"⏭️  Skipping error {idx} for URL: {url} - Missing line/column numbers (line: {line}, column: {column})")
                continue
            
            # Skip errors with too long context (>= 1000 tokens)
            if max_tokens >= 1000:
                skipped_count += 1
                print(f"⏭️  Skipping error {idx} for URL: {url} - Context too long ({max_tokens} tokens)")
                continue
            
            try:
                processed_count += 1
                print(f"\n{'='*80}")
                print(f"Processing error {processed_count}/{total_errors} - Error {idx} for URL: {url}")
                print(f"Line: {line}, Column: {column}, Max tokens: {max_tokens}")
                print(f"Error description: {error.get('error_description', '')}")
                print(f"Error snippet: {error.get('error_part_in_code', '')}")
                print(f"Code context: {error.get('context_code', '')[:100]} ...")
                print(f"{'='*80}")

                error_key = f"error_{hash_url(url)}_{idx}"
                error_input = {
                    error_key: {
                        "error_description": error.get("error_description", ""),
                        "error_snippet": error.get("error_part_in_code", ""),
                        "code_context": error.get("context_code", "")
                    }
                }

                # Create tasks
                analyze_task = agents.analyze_errors_task(error_input)
                fix_task = agents.fix_errors_task(error_input, analyzer_output=analyze_task)
                fix_task.context = [analyze_task]

                # Create and run the crew
                crew = Crew(
                    agents=[agents.expert_Javascript_error_analyzer(), agents.expert_Javascript_fix_suggestor()],
                    tasks=[analyze_task, fix_task],
                    process=Process.sequential,
                    verbose=True,
                    memory=False
                )
                
                print(f"Starting CrewAI processing for error {processed_count}...")
                result = crew.kickoff()
                print(f"CrewAI processing completed for error {processed_count}")

                # Extract agent responses from the result
                agent1_response = ""
                agent2_response = ""
                
                # Convert result to dict if possible
                if hasattr(result, 'dict'):
                    result_dict = result.dict()
                elif hasattr(result, 'to_dict'):
                    result_dict = result.to_dict()
                else:
                    result_dict = {"raw_result": str(result)}
                
                # Extract Agent1 response (suggestion) - from the first task
                '''if 'tasks_outputs' in result_dict and len(result_dict['tasks_outputs']) > 0:
                    agent1_response = result_dict['tasks_outputs'][0] if len(result_dict['tasks_outputs']) > 0 else ""
                
                # Extract Agent2 response (fixed code) - from the second task
                if 'tasks_outputs' in result_dict and len(result_dict['tasks_outputs']) > 1:
                    agent2_response = result_dict['tasks_outputs'][1] if len(result_dict['tasks_outputs']) > 1 else ""'''
                agent1_response = analyze_task.output.raw if hasattr(analyze_task.output, 'raw') else str(analyze_task.output)
                agent2_response = fix_task.output.raw if hasattr(fix_task.output, 'raw') else str(fix_task.output)

                # Collect the result for each error with the exact structure requested
                result_entry = {
                    "error_description": error.get("error_description", ""),
                    "error_snippet": error.get("error_part_in_code", ""),
                    "code_context": error.get("context_code", ""),
                    "agent1_response": agent1_response,  # Suggestion from Expert JavaScript Error Analyzer
                    "agent2_response": agent2_response   # Fixed code from Expert JavaScript Fix Suggestor
                }
                all_results.append(result_entry)
                
                # Save results after each iteration to prevent data loss
                with open("all_results.json", "w", encoding="utf-8") as outf:
                    json.dump(all_results, outf, indent=2)
                
                print(f"✅ Successfully processed and saved error {processed_count}/{total_errors} for URL: {url}")
                
            except Exception as e:
                print(f"❌ ERROR processing error {processed_count}/{total_errors} for URL: {url}")
                print(f"Error details: {str(e)}")
                print(f"Error type: {type(e).__name__}")
                
                # Add error entry to results
                error_entry = {
                    "error_description": error.get("error_description", ""),
                    "error_snippet": error.get("error_part_in_code", ""),
                    "code_context": error.get("context_code", ""),
                    "agent1_response": agent1_response,
                    "agent2_response": agent2_response
                }
                all_results.append(error_entry)
                
                # Save results even after error
                with open("all_results.json", "w", encoding="utf-8") as outf:
                    json.dump(all_results, outf, indent=2)
                
                print(f"⚠️  Added error entry and saved progress. Continuing with next error...")
                continue

    print(f"\n🎉 Processing completed!")
    print(f"📊 Summary:")
    print(f"   - Total errors in file: {total_errors}")
    print(f"   - Errors processed: {processed_count}")
    print(f"   - Errors skipped: {skipped_count}")
    print(f"   - Final results saved to all_results.json with {len(all_results)} entries.") 