from crewai import Agent, Task, Crew
from typing import List, Dict, Any
from dotenv import load_dotenv
import os

load_dotenv()

class ErrorAnalysisAgents:
    def __init__(self):
        self.error_analyzer = Agent(
            role='JavaScript Error Analyzer',
            goal='Analyze JavaScript errors and identify their root causes',
            backstory="""You are an expert JavaScript developer with deep knowledge of 
            browser environments and error patterns. You can analyze stack traces and 
            identify the root causes of JavaScript errors.""",
            verbose=True
        )

        self.error_fixer = Agent(
            role='JavaScript Error Fixer',
            goal='Provide solutions and fixes for identified JavaScript errors',
            backstory="""You are a senior JavaScript developer with extensive experience 
            in fixing complex browser-related issues. You can provide detailed solutions 
            and code fixes for various JavaScript errors.""",
            verbose=True
        )

    def analyze_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze errors using CrewAI agents."""
        analysis_task = Task(
            description=f"""Analyze these JavaScript errors and provide detailed information:
            {errors}
            
            For each error, provide:
            1. Root cause analysis
            2. Impact on user experience
            3. Whether it's a critical issue
            4. Potential user interactions that might have triggered it""",
            agent=self.error_analyzer,
            expected_output="A detailed analysis of each error including root cause, impact assessment, criticality level, and potential triggers"
        )

        fix_task = Task(
            description="""Based on the error analysis, provide:
            1. Specific code fixes
            2. Best practices to prevent similar errors
            3. Performance optimization suggestions
            4. Testing recommendations""",
            agent=self.error_fixer,
            expected_output="A comprehensive solution including code fixes, best practices, performance optimizations, and testing recommendations"
        )

        crew = Crew(
            agents=[self.error_analyzer, self.error_fixer],
            tasks=[analysis_task, fix_task],
            verbose=True
        )

        result = crew.kickoff()
        return result 