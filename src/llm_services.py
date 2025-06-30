from langchain_anthropic import ChatAnthropic
from langchain_fireworks import ChatFireworks, FireworksEmbeddings
# from langchain_google_genai import ChatGoogleGenerativeAI
from langfuse.langchain import CallbackHandler

import config
from logger import logger

langfuse_handler = CallbackHandler()

# ------------------------------------------------------------
# LLM
# ------------------------------------------------------------

def get_llm():
    """Initialize and return the specified LLM"""

    logger.info(f"Using model: {config.MODEL}")

    if config.PROVIDER == "anthropic":
        return ChatAnthropic(api_key=config.ANTHROPIC_API_KEY, model=config.MODEL, max_tokens=config.MAX_TOKENS, temperature=config.TEMPERATURE)#thinking={"type": "enabled", "budget_tokens": 10000})
    elif config.PROVIDER == "fireworks":
        return ChatFireworks(api_key=config.FIREWORKS_API_KEY, model=config.MODEL, max_tokens=100000, temperature=config.TEMPERATURE)
    # elif provider == "google":
    #     return ChatGoogleGenerativeAI(api_key=config.GOOGLE_API_KEY, model=model, max_tokens=20000, temperature=0.2)
    else:
        raise ValueError(f"Unsupported provider: {config.PROVIDER}")

# ------------------------------------------------------------
# Invoke LLM
# ------------------------------------------------------------

async def run_llm_natively(prompt: str) -> str:
    llm = get_llm()
    response = await llm.ainvoke(prompt, config={"callbacks": [langfuse_handler]})
    return response.content.strip()


# ------------------------------------------------------------
# Embeddings
# ------------------------------------------------------------

async def get_embeddings(texts: list[str]) -> list[list[float]]:
    embeddings = FireworksEmbeddings(api_key=config.FIREWORKS_API_KEY, model=config.FIREWORKS_EMBEDDING_MODEL)
    return await embeddings.aembed_documents(texts)



