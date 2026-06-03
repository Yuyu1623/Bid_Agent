# 这个脚本负责统一调用大模型，支持同步和异步请求。
import os
import asyncio
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

    def think(self, messages: List[Dict[str, str]], temperature: float = 0) -> str:
        print(f"\n[模型调用] model={self.model}")
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
        """Asynchronous model call for concurrent long-form generation tasks."""
        print(f"\n[async model call] model={self.model}")

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

    async def think_many(
        self,
        messages_batch: Sequence[List[Dict[str, str]]],
        temperature: float = 0,
        max_concurrency: Optional[int] = None,
    ) -> List[str]:
        """Run multiple independent prompts concurrently and keep result order."""
        concurrency = max_concurrency or int(os.getenv("LLM_MAX_CONCURRENCY", "5"))
        semaphore = asyncio.Semaphore(concurrency)

        async def run_one(messages: List[Dict[str, str]]) -> str:
            async with semaphore:
                return await self.athink(messages, temperature=temperature)

        return await asyncio.gather(*(run_one(messages) for messages in messages_batch))

    def think_many_sync(
        self,
        messages_batch: Sequence[List[Dict[str, str]]],
        temperature: float = 0,
        max_concurrency: Optional[int] = None,
    ) -> List[str]:
        """Synchronous wrapper around think_many for scripts without an event loop."""
        return asyncio.run(
            self.think_many(
                messages_batch,
                temperature=temperature,
                max_concurrency=max_concurrency,
            )
        )

'''
# 调用实例
import asyncio
from llm_client import LLM_Invoke

async def main():
    llm = LLM_Invoke()

    results = await llm.think_many([
        [{"role": "user", "content": "写服务承诺"}],
        [{"role": "user", "content": "写质量保障方案"}],
    ])

    print(results)

asyncio.run(main())
'''
