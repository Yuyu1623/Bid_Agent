# -*- coding: utf-8 -*-
"""LLM client helpers for synchronous and asynchronous OpenAI-compatible calls."""

import asyncio
import os
from typing import Dict, List, Optional, Sequence

from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAI


load_dotenv()


class LLM_Invoke:
    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.model = model or os.getenv("LLM_MODEL_ID")
        api_key = api_key or os.getenv("LLM_API_KEY")
        base_url = base_url or os.getenv("LLM_BASE_URL")
        self.timeout = timeout or int(os.getenv("LLM_TIMEOUT", "120"))

        if not all([self.model, api_key, base_url]):
            raise ValueError(
                "请先配置 LLM_MODEL_ID、LLM_API_KEY、LLM_BASE_URL。"
                "可以复制 .env.example 为 .env 后填写。"
            )

        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=self.timeout)
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=self.timeout,
        )

    def think(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        stream: bool = True,
    ) -> str:
        """Call the model synchronously and optionally stream chunks to stdout."""
        print(f"\n[model call] model={self.model}, stream={stream}")
        if not stream:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
            content = response.choices[0].message.content or ""
            print(content)
            return content

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )

        chunks: List[str] = []
        for chunk in response:
            content = chunk.choices[0].delta.content or ""
            print(content, end="", flush=True)
            chunks.append(content)
        print()
        return "".join(chunks)

    async def athink(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        stream: bool = False,
    ) -> str:
        """Call the model asynchronously and optionally stream chunks to stdout."""
        print(f"\n[async model call] model={self.model}, stream={stream}")

        if stream:
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )

            chunks: List[str] = []
            async for chunk in response:
                content = chunk.choices[0].delta.content or ""
                print(content, end="", flush=True)
                chunks.append(content)
            print()
            return "".join(chunks)

        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content or ""

    async def astream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
    ):
        """Yield streamed text chunks from one chat completion."""
        print(f"\n[async stream model call] model={self.model}")
        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in response:
            content = chunk.choices[0].delta.content or ""
            if content:
                print(content, end="", flush=True)
                yield content
        print()

    async def think_many(
        self,
        messages_batch: Sequence[List[Dict[str, str]]],
        temperature: float = 0,
        max_concurrency: Optional[int] = None,
        stream: bool = False,
    ) -> List[str]:
        """Run multiple independent prompts concurrently and keep result order."""
        concurrency = max_concurrency or int(os.getenv("LLM_MAX_CONCURRENCY", "5"))
        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(messages: List[Dict[str, str]]) -> str:
            async with semaphore:
                return await self.athink(messages, temperature=temperature, stream=stream)

        return await asyncio.gather(*(run_one(messages) for messages in messages_batch))

    def think_many_sync(
        self,
        messages_batch: Sequence[List[Dict[str, str]]],
        temperature: float = 0,
        max_concurrency: Optional[int] = None,
        stream: bool = False,
    ) -> List[str]:
        """Synchronous wrapper around think_many for scripts without an event loop."""
        return asyncio.run(
            self.think_many(
                messages_batch,
                temperature=temperature,
                max_concurrency=max_concurrency,
                stream=stream,
            )
        )
