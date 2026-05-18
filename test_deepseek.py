#!/usr/bin/env python3
"""
Test script for the DeepSeek API integration.
This script loads settings from .env and verifies the connection to the DeepSeek API.
"""

import os
import sys
import time
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

# Get DeepSeek config
api_key = os.getenv("DEEPSEEK_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

print("=" * 60)
print("             DEEPSEEK API TEST DIAGNOSTIC")
print("=" * 60)
print(f"Base URL: {base_url}")

if api_key:
    # Obfuscate the key for security in logs
    masked_key = f"{api_key[:6]}...{api_key[-6:]}" if len(api_key) > 12 else "Too short"
    print(f"API Key:  {masked_key} (Found)")
else:
    print("API Key:  NOT FOUND in environment or .env file!")
print("-" * 60)

if not api_key:
    print("[-] ERROR: DEEPSEEK_API_KEY is missing!")
    print("    Please check that you have a .env file containing:")
    print("    DEEPSEEK_API_KEY=your_actual_api_key_here")
    sys.exit(1)

try:
    print("[*] Importing openai library...")
    from openai import OpenAI
except ImportError:
    print("[-] ERROR: The 'openai' package is not installed in this environment.")
    print("    Please install it using: pip install openai")
    sys.exit(1)

try:
    print("[*] Initializing OpenAI client for DeepSeek...")
    client = OpenAI(api_key=api_key, base_url=base_url)

    test_prompt = (
        "Introduce yourself in detail. What is your model name, version, and architecture? "
        "What is your training data knowledge cutoff? What are your key features, capabilities, "
        "and primary strengths compared to other models? Please respond with a comprehensive and structured overview."
    )
    print(f"[*] Sending prompt: \"{test_prompt}\"")
    print("[*] Calling deepseek-chat model...")
    
    start_time = time.time()
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a highly knowledgeable, precise AI model expert explaining your own architecture and capabilities."},
            {"role": "user", "content": test_prompt}
        ],
        stream=False,
        temperature=0.7
    )
    end_time = time.time()
    elapsed = end_time - start_time

    print("\n[+] SUCCESS: Received response from DeepSeek API!")
    print(f"    Latency: {elapsed:.2f} seconds")
    print(f"    Model:   {response.model}")
    print("-" * 60)
    print("Response Content:")
    print(response.choices[0].message.content.strip())
    print("-" * 60)
    
    if response.usage:
        print("Usage details:")
        print(f"  - Prompt Tokens:     {response.usage.prompt_tokens}")
        print(f"  - Completion Tokens: {response.usage.completion_tokens}")
        print(f"  - Total Tokens:      {response.usage.total_tokens}")
    print("=" * 60)

except Exception as e:
    print("\n[-] ERROR: Failed to communicate with the DeepSeek API.")
    print(f"    Type:    {type(e).__name__}")
    print(f"    Message: {e}")
    print("\nTroubleshooting steps:")
    print("1. Double check that your API key in .env is correct.")
    print("2. Ensure your base URL (https://api.deepseek.com) is reachable and not blocked by a firewall.")
    print("3. Check if your DeepSeek account has sufficient credit/balance.")
    print("=" * 60)
    sys.exit(1)
