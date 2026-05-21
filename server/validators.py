from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CompileRequest(BaseModel):
    source: str = Field(..., max_length=524_288)
    optimization_level: int = Field(default=1, ge=0, le=3)
    stdin: Optional[str] = Field(default='', max_length=65_536)
    include_explanation: bool = False


class CheckRequest(BaseModel):
    source: str = Field(..., max_length=524_288)


class ConvertRequest(BaseModel):
    direction: Literal['c_to_blocks', 'blocks_to_c']
    source: str = Field(default='', max_length=524_288)
    workspace: dict[str, Any] = Field(default_factory=dict)


class DebugStartRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=524_288)


class ValidateFileRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    content: str = Field(..., max_length=2_097_152)
    file_type: Literal['c', 'asm', 'scratch', 'cfproj']


class ExplainRequest(BaseModel):
    source: str = Field(..., max_length=524_288)


class FlowchartRequest(BaseModel):
    source: str = Field(..., max_length=524_288)
