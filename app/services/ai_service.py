import json
import asyncio
import logging
import datetime
from typing import List, Dict, Any
from openai import OpenAI
from app.core.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, PROMPTS_DIR, RESPONSES_DIR

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=300.0
        )

    def _repair_json(self, json_str: str) -> str:
        """Attempts to repair truncated or malformed JSON from AI."""
        json_str = json_str.strip()
        if not json_str:
            return "{}"
        
        # If it's already valid, return it
        try:
            json.loads(json_str)
            return json_str
        except json.JSONDecodeError:
            pass

        # Naive quote balancing
        # We need to be careful about escaped quotes
        quotes = 0
        escaped = False
        for char in json_str:
            if char == '\\' and not escaped:
                escaped = True
            elif char == '"' and not escaped:
                quotes += 1
                escaped = False
            else:
                escaped = False
        
        if quotes % 2 != 0:
            json_str += '"'

        # Remove trailing commas or colons which would make it invalid after closing
        json_str = json_str.rstrip()
        while json_str and json_str[-1] in (',', ':'):
            json_str = json_str[:-1].rstrip()

        # Close open braces and brackets
        stack = []
        in_string = False
        escaped = False
        for char in json_str:
            if char == '"' and not escaped:
                in_string = not in_string
            
            if not in_string:
                if char == '{':
                    stack.append('}')
                elif char == '[':
                    stack.append(']')
                elif char == '}':
                    if stack and stack[-1] == '}':
                        stack.pop()
                elif char == ']':
                    if stack and stack[-1] == ']':
                        stack.pop()
            
            if char == '\\' and not escaped:
                escaped = True
            else:
                escaped = False
        
        while stack:
            json_str += stack.pop()
            
        return json_str

    async def call_ai(self, prompt: str) -> Dict[str, Any]:
        """Helper to call DeepSeek AI asynchronously."""
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts visual keywords from scripts. Output strictly valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                max_tokens=8192
            )
            content = response.choices[0].message.content
            
            try:
                return json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                # Save problematic response for debugging
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_file = RESPONSES_DIR / f"failed_response_{timestamp}.json"
                with open(debug_file, "w") as f:
                    f.write(content)
                logger.info(f"Saved failed response to {debug_file}")
                
                # Try to repair
                repaired_content = self._repair_json(content)
                return json.loads(repaired_content)
                
        except Exception as e:
            logger.error(f"Error calling AI: {e}")
            raise

    def get_prompt(self, source: str) -> str:
        """Loads a prompt template from the resources directory."""
        filename = f"prompt_{source}.txt"
        prompt_path = PROMPTS_DIR / filename
        if not prompt_path.exists():
            # Fallback to general photography if specific prompt doesn't exist
            prompt_path = PROMPTS_DIR / "prompt_photography.txt"
        
        with open(prompt_path, "r") as f:
            return f.read()

    async def process_script(self, script_text: str, source: str) -> Dict[str, Any]:
        """Processes a script using AI to extract segments and keywords."""
        if source == "both":
            prompt_pin = self.get_prompt("pinterest").replace("{script_text}", script_text)
            prompt_uns = self.get_prompt("unsplash").replace("{script_text}", script_text)
            
            res_pin, res_uns = await asyncio.gather(self.call_ai(prompt_pin), self.call_ai(prompt_uns))
            
            segs_pin = res_pin.get("segments", res_pin)
            segs_uns = res_uns.get("segments", res_uns)
            
            merged_segments = []
            for i in range(max(len(segs_pin), len(segs_uns))):
                s_pin = segs_pin[i] if i < len(segs_pin) else {"text": "", "keywords": [], "id": i}
                s_uns = segs_uns[i] if i < len(segs_uns) else {"text": "", "keywords": [], "id": i}
                
                merged_segments.append({
                    "id": s_pin.get("id", i),
                    "text": s_pin.get("text") or s_uns.get("text"),
                    "keywords": s_pin.get("keywords", []) + ["|"] + s_uns.get("keywords", [])
                })
            return {"segments": merged_segments}
        else:
            prompt = self.get_prompt(source).replace("{script_text}", script_text)
            return await self.call_ai(prompt)

ai_service = AIService()
