from openai import AsyncOpenAI
from .config import LLM_MODEL, LLM_BASE_URL, LLM_API_KEY


async def get_llm_response(prompt: str) -> str:
    """Get response from LLM service."""
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY is not set. Please set it in environment variables or .env file")
    
    client = AsyncOpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )

    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    return response.choices[0].message.content.strip() 