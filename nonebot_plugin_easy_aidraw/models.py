from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ImageData(BaseModel):
    b64_json: Optional[str] = None
    url: Optional[str] = None
    revised_prompt: Optional[str] = None


class Usage(BaseModel):
    input_tokens: Optional[int] = None
    input_tokens_details: Optional[Dict] = None
    output_tokens: Optional[int] = None
    output_tokens_details: Optional[Dict] = None
    total_tokens: Optional[int] = None


class ImageResponse(BaseModel):
    created: Optional[int] = None
    data: List[ImageData] = Field(default_factory=list)
    background: Optional[str] = None
    output_format: Optional[str] = None
    quality: Optional[str] = None
    size: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Usage] = None
    error: Optional[Dict] = None
