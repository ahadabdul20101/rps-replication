
#   "gpt-4o"                 → AzureOpenAI 
#   "Llama-3.3-70B-Instruct" → plain OpenAI 
# Same API key for both — same Azure resource.


import os
import time
import httpx
from openai import AzureOpenAI, OpenAI

import config


def _get_client(model_id: str):
    api_key = os.environ.get("AZURE_API_KEY", config.AZURE_API_KEY)

    if model_id == "gpt-4o":
        return AzureOpenAI(
            api_key        = api_key,
            azure_endpoint = config.AZURE_ENDPOINT,
            api_version    = config.AZURE_API_VERSION,
        )
    else:
        # Llama on Azure Foundry — uses plain OpenAI client
        return OpenAI(
            api_key  = api_key,
            base_url = config.AZURE_ENDPOINT_LLAMA,
        )


def call_model(model_id: str, system_prompt: str, user_prompt: str) -> str | None:
    """
    Send a prompt and return the response text.
    Retries up to MAX_RETRIES times on failure.
    Returns None if all retries fail.
    """
    client = _get_client(model_id)

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model       = model_id,
                max_tokens  = config.MAX_TOKENS,
                temperature = config.TEMPERATURE,
                messages    = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
            )
            return response.choices[0].message.content

        except Exception as e:
            print(f"    [API] Attempt {attempt}/{config.MAX_RETRIES} failed: {e}")
            if attempt < config.MAX_RETRIES:
                time.sleep(config.SLEEP_ON_RETRY)

    return None
