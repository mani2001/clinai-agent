"""
Simplified LLM calling functionality using HTTP requests.
This avoids Groq client version issues by using direct API calls.
"""

import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get GROQ API key from environment variables
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables")

# Constants
MODEL = "llama-3.3-70b-versatile"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

def call_llm(prompt: str, temperature: float = 0.0, max_tokens: int = 2048) -> str:
    """
    Call the GROQ LLM with a prompt and return the response using direct HTTP requests.
    
    Args:
        prompt: The prompt to send to the LLM
        temperature: Sampling temperature (lower = more deterministic)
        max_tokens: Maximum number of tokens to generate
        
    Returns:
        str: The LLM's response
    """
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json"
    }
    
    # Prepare request body
    data = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        # Make the API request
        response = requests.post(API_URL, headers=headers, json=data)
        
        # Check for errors
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        
        # Extract and return the generated text
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error calling GROQ API: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response status: {e.response.status_code}")
            print(f"Response text: {e.response.text}")
        return ""

# For testing the connection
if __name__ == "__main__":
    test_prompt = "Hello, can you confirm that you're working? Please respond with a short confirmation."
    print("Testing GROQ API connection...")
    response = call_llm(test_prompt)
    print(f"LLM Response: {response}")