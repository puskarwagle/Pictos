import asyncio
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ai_service import ai_service

async def test_chunking():
    script_path = "scripts-backups/adhd-english.md"
    if not os.path.exists(script_path):
        print(f"Error: {script_path} not found.")
        return

    with open(script_path, "r") as f:
        script_text = f.read()

    print(f"Processing script ({len(script_text)} characters)...")
    try:
        result = await ai_service.process_script_dense(script_text)
        
        segments = result.get("segments", [])
        print(f"Success! Processed {len(segments)} segments.")
        
        if segments:
            last_seg = segments[-1]
            print(f"Last segment ID: {last_seg['id']}")
            print(f"Last segment text sample: {last_seg['full_text'][:50]}...")
            
            # Save for inspection
            output_file = "data/ai_responses/test_chunked_output.json"
            with open(output_file, "w") as f:
                json.dump(result, f, indent=4)
            print(f"Full output saved to {output_file}")
        else:
            print("No segments returned.")
            
    except Exception as e:
        print(f"Failed to process script: {e}")

if __name__ == "__main__":
    asyncio.run(test_chunking())
