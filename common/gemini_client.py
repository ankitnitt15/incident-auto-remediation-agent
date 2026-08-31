import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

_DEFAULT_MODEL = "gemini-2.5-flash"
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def generate_content(contents, **kwargs):
    return _client.models.generate_content(
        model=_DEFAULT_MODEL,
        contents=contents,
        **kwargs,
    )
