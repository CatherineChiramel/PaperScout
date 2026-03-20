import os

from dotenv import load_dotenv

load_dotenv()


def get_llm(provider: str, model: str):
    """Create a LangChain chat model for the given provider and model.

    Supported providers: google, groq, xai
    """
    if provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=os.environ["GOOGLE_API_KEY"],
        )
    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            api_key=os.environ["GROQ_API_KEY"],
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Supported: google, groq, xai")
