
"""LLM client (Gemini or OpenAI-compatible).
Returns validated JSON. Never fabricates output on failure.
"""
import json
import re
import logging
import os
import time

import httpx
from pydantic import BaseModel, ValidationError

from .config import settings

log = logging.getLogger("llm")

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class LLMError(Exception):
    pass


def configured() -> bool:
    if settings.llm_provider == "gemini":
        return bool(settings.gemini_key)
    return bool(settings.openai_key)


def _gemini_request(
    prompt: str,
    system: str,
    temperature: float,
    model_name: str,
) -> str:
    """Call Gemini and retry temporary provider errors."""
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model_name}:generateContent"
    )

    body = {
        "systemInstruction": {
            "parts": [{"text": system}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(3):
        try:
            response = httpx.post(
                url,
                json=body,
                headers={"x-goog-api-key": settings.gemini_key},
                timeout=90,
            )

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt < 2:
                    wait_seconds = 2 ** (attempt + 1)
                    log.warning(
                        "Gemini returned HTTP %s. Retrying in %s seconds...",
                        response.status_code,
                        wait_seconds,
                    )
                    time.sleep(wait_seconds)
                    continue

            response.raise_for_status()

            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            message = error.response.text[:300]
            raise LLMError(
                f"Gemini model '{model_name}' returned HTTP {status}: {message}"
            ) from error

        except (httpx.TimeoutException, httpx.NetworkError) as error:
            if attempt < 2:
                wait_seconds = 2 ** (attempt + 1)
                log.warning(
                    "Gemini connection failed. Retrying in %s seconds...",
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue

            raise LLMError(f"Gemini connection failed: {error}") from error

        except (KeyError, IndexError, ValueError) as error:
            raise LLMError(
                f"Gemini returned an unexpected response: {error}"
            ) from error

    raise LLMError("Gemini request failed after retries.")


def _call(
    prompt: str,
    system: str,
    temperature: float = 0.7,
) -> str:
    if not configured():
        raise LLMError(
            f"No API key configured for LLM provider "
            f"'{settings.llm_provider}'. Set it in backend/.env"
        )

    if settings.llm_provider == "gemini":
        primary_model = settings.gemini_model

        # Configure another model in backend/.env if needed.
        fallback_model = os.getenv(
            "GEMINI_FALLBACK_MODEL",
            "gemini-3.5-flash-lite",
        ).strip()

        models_to_try = [primary_model]

        if fallback_model and fallback_model != primary_model:
            models_to_try.append(fallback_model)

        errors = []

        for model_name in models_to_try:
            try:
                log.info("Trying Gemini model: %s", model_name)

                return _gemini_request(
                    prompt,
                    system,
                    temperature,
                    model_name,
                )

            except LLMError as error:
                errors.append(str(error))
                log.warning(
                    "Gemini model %s failed: %s",
                    model_name,
                    error,
                )

        raise LLMError(
            "All configured Gemini models failed. "
            + " | ".join(errors)
        )

    # OpenAI-compatible provider
    body = {
        "model": settings.openai_model,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        response = httpx.post(
            f"{settings.openai_base}/chat/completions",
            json=body,
            headers={
                "Authorization": f"Bearer {settings.openai_key}"
            },
            timeout=90,
        )

        response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]

    except httpx.HTTPStatusError as error:
        raise LLMError(
            f"LLM provider returned HTTP "
            f"{error.response.status_code}: "
            f"{error.response.text[:200]}"
        ) from error

    except (httpx.HTTPError, KeyError, IndexError) as error:
        raise LLMError(f"LLM request failed: {error}") from error


def _parse(text: str) -> dict:
    cleaned = re.sub(
        r"^```(?:json)?|```$",
        "",
        text.strip(),
        flags=re.M,
    ).strip()

    return json.loads(cleaned)


def generate_json(
    prompt: str,
    model: type[BaseModel],
    system: str,
    temperature: float = 0.7,
    retries: int = 2,
):
    last_error = None

    for attempt in range(retries):
        raw = _call(prompt, system, temperature)

        try:
            return model.model_validate(_parse(raw))

        except (json.JSONDecodeError, ValidationError) as error:
            last_error = error
            log.warning(
                "LLM returned invalid JSON. Attempt %s: %s",
                attempt + 1,
                error,
            )

    raise LLMError(
        f"LLM returned invalid structured output: {last_error}"
    )
