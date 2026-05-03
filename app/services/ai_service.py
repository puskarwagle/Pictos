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

        # Track state to close properly
        stack = []
        in_string = False
        escaped = False
        
        fixed_str = ""
        for i, char in enumerate(json_str):
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
            fixed_str += char

        # If we are inside a string at the end, close it
        if in_string:
            fixed_str += '"'
        
        # Iteratively remove trailing problematic characters
        while True:
            fixed_str = fixed_str.rstrip()
            if not fixed_str:
                break
            
            last_char = fixed_str[-1]
            
            # Remove trailing delimiters that have no following value
            if last_char in (',', ':', '{', '['):
                if last_char in ('{', '['):
                    if stack: stack.pop()
                fixed_str = fixed_str[:-1]
                continue
            
            # If it ends with a quote, check if it's a key without a colon
            # or a value that we just closed.
            if last_char == '"':
                # Find the start of this string
                start_quote = -1
                for j in range(len(fixed_str) - 2, -1, -1):
                    if fixed_str[j] == '"':
                        # Count backslashes before this quote to handle escapes
                        temp_bs = 0
                        for k in range(j-1, -1, -1):
                            if fixed_str[k] == '\\': temp_bs += 1
                            else: break
                        if temp_bs % 2 == 0:
                            start_quote = j
                            break
                
                if start_quote != -1:
                    before_str = fixed_str[:start_quote].rstrip()
                    # A string is a KEY if it's preceded by { or ,
                    # A string is a VALUE if it's preceded by : or [
                    if before_str and before_str[-1] in ('{', ','):
                        # It could be a key OR a value in an array.
                        # If the stack says we're in an object, it's a key.
                        if stack and stack[-1] == '}':
                            # This is a key. Since no colon follows, it's truncated.
                            fixed_str = before_str
                            continue
            
            break

        # Close all open braces/brackets
        while stack:
            fixed_str += stack.pop()
            
        return fixed_str

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
                try:
                    return json.loads(repaired_content)
                except json.JSONDecodeError as e2:
                    logger.error(f"Repair failed: {e2}")
                    logger.error(f"Repaired content: {repaired_content}")
                    raise
                
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

    def load_manifest(self) -> str:
        """Loads the providers manifest as a string for prompting."""
        manifest_path = PROMPTS_DIR.parent / "providers_manifest.json"
        if manifest_path.exists():
            with open(manifest_path, "r") as f:
                return f.read()
        return "[]"

    def _chunk_script(self, script_text: str, max_chars: int = 1500) -> List[str]:
        """Splits a long script into manageable chunks for AI processing."""
        if len(script_text) <= max_chars:
            return [script_text]

        chunks = []
        remaining = script_text

        while remaining:
            if len(remaining) <= max_chars:
                chunks.append(remaining)
                break

            # Try to find the best split point within the max_chars limit
            search_window = remaining[:max_chars]
            
            # 1. Try double newline (paragraph)
            split_idx = search_window.rfind("\n\n")
            
            # 2. Try single newline (sentence)
            if split_idx == -1:
                split_idx = search_window.rfind("\n")
            
            # 3. Try space (word)
            if split_idx == -1:
                split_idx = search_window.rfind(" ")
            
            # 4. Hard cut (if no separators found, which is unlikely)
            if split_idx == -1:
                split_idx = max_chars

            chunks.append(remaining[:split_idx].strip())
            remaining = remaining[split_idx:].strip()

        return chunks

    async def process_script(self, script_text: str, source: str = "dense") -> Dict[str, Any]:
        """Processes a script using AI to extract segments and keywords."""
        return await self.process_script_dense(script_text)

    async def process_script_dense(self, script_text: str) -> Dict[str, Any]:
        """Multi-step high-density visual mapping pipeline with parallel chunking."""
        # 1. Vibe Analysis (Full script for global context)
        vibe_prompt = self.get_prompt("vibe_analysis").replace("{script_text}", script_text)
        vibe_analysis = await self.call_ai(vibe_prompt)
        
        # 2. Chunking
        chunks = self._chunk_script(script_text, max_chars=1500)
        logger.info(f"Split script into {len(chunks)} chunks for processing.")
        
        # 3. Concurrent Dense Mapping
        manifest = self.load_manifest()
        mapping_template = self.get_prompt("dense_mapping")\
            .replace("{providers_manifest}", manifest)\
            .replace("{vibe_analysis}", json.dumps(vibe_analysis, indent=2))
        
        tasks = []
        for chunk in chunks:
            prompt = mapping_template.replace("{script_text}", chunk)
            tasks.append(self.call_ai(prompt))
        
        # Gather all chunk results
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 4. Merge and Renumber
        all_segments = []
        for i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                logger.error(f"Chunk {i} failed: {result}")
                continue
            
            segments = result.get("segments", [])
            all_segments.extend(segments)
        
        # Re-assign IDs and post-process
        for idx, seg in enumerate(all_segments):
            seg["id"] = idx + 1
            
            # Transform anchors into UI-compatible keywords
            all_keywords = []
            for anchor in seg.get("anchors", []):
                provider = anchor.get("provider", "pinterest")
                keywords = [f"{provider}:{k}" for k in anchor.get("keywords", [])]
                all_keywords.extend(keywords)
                all_keywords.append("|")
            
            if all_keywords and all_keywords[-1] == "|":
                all_keywords.pop()
                
            seg["keywords"] = all_keywords
            seg["text"] = seg.get("full_text", "")
            
        return {"segments": all_segments, "vibe": vibe_analysis}

ai_service = AIService()
