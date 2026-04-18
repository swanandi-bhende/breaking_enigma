from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.output_parsers import PydanticOutputParser
from langchain_core.pydantic_v1 import BaseModel
from typing import Any, Dict, List, Optional
import json

from .config import settings


class LLMClient:
    """Unified LLM client for all agents."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.chat = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.7,
            api_key=settings.OPENAI_API_KEY,
        )
        self.embeddings = OpenAIEmbeddings(
            model=settings.OPENAI_EMBEDDING_MODEL, api_key=settings.OPENAI_API_KEY
        )

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Execute chat completion and return content."""
        kwargs = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    async def structured_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],
        temperature: float = 0.3,
        max_retries: int = 3,
    ) -> BaseModel:
        """Get structured JSON output using Pydantic schema."""
        parser = PydanticOutputParser(pydantic_object=output_schema)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt + "\n\n{format_instructions}"),
                ("human", user_prompt),
            ]
        )

        chain = prompt | self.chat | parser

        last_error = None
        for attempt in range(max_retries):
            try:
                result = await chain.ainvoke(
                    {"format_instructions": parser.get_format_instructions()}
                )
                return result
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    continue

        raise last_error

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed texts and return vectors."""
        return await self.embeddings.aembed_documents(texts)

    async def embed_query(self, query: str) -> List[float]:
        """Embed a single query."""
        return await self.embeddings.aembed_query(query)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text (approximate)."""
        return len(text) // 4


llm_client = LLMClient()
