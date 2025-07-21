import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
import re
load_dotenv()

def initialize_genai():
    api_key = os.getenv("api_khantouch")
    if not api_key:
        raise RuntimeError("Aucun API key trouvé pour Gemini dans .env")
    genai.configure(api_key=api_key)

initialize_genai()

with open("app/data/gemini_guided_prompts.json", "r", encoding="utf-8") as f:
    GUIDED_PROMPTS = json.load(f)

def ask_gemini(validation_type: str, user_input: str) -> dict:
    """
    Uses both the description and example_prompt_format from GUIDED_PROMPTS[validation_type]
    to craft a rich and guided prompt for Gemini.
    """
    template = GUIDED_PROMPTS.get(validation_type)
    if template is None:
        return {"error": f"No guided prompt for validation '{validation_type}'"}

    # Combine description and example prompt
    description = template["description"].replace('<USER_PROMPT>',user_input).strip()
    example = template["example_prompt_format"].replace("<USER_INPUT_HERE>", user_input).strip()

    raw_prompt = f"{description}"

    # Call Gemini
    model = genai.GenerativeModel("models/gemini-2.0-flash")
    g_response = model.generate_content(raw_prompt)
    raw_text = g_response.text.strip()

    # Strip markdown-style code fences
    cleaned = raw_text
    fence_pattern = r"^```(?:json)?\s*(\{.*?\})\s*```$"
    m = re.search(fence_pattern, raw_text, re.DOTALL)
    if m:
        cleaned = m.group(1).strip()
    else:
        if raw_text.startswith("```"):
            lines = raw_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

    # Attempt JSON parse
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"error": "invalid_json", "raw_text": raw_text}

    return parsed
