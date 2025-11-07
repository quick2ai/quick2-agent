import os
import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from libs.common.models import ExecutionStep

app = FastAPI(title="Executor Service", version="1.0.0")
FastAPIInstrumentor.instrument_app(app)


class ExecuteRequest(BaseModel):
    step: ExecutionStep
    task_context: Dict[str, Any] = {}


class ToolExecutor:
    """Stub implementations for all 10 tools with deterministic mocks"""
    
    @staticmethod
    def browser(params: dict) -> dict:
        url = params.get("url", "https://example.com")
        return {
            "tool": "browser",
            "status": "success",
            "result": f"Fetched content from {url}",
            "artifact_uri": f"minio://artifacts/browser_{hash(url) % 10000}.html",
            "metadata": {"url": url, "status_code": 200}
        }
    
    @staticmethod
    def pdf_parser(params: dict) -> dict:
        file_path = params.get("file_path", "document.pdf")
        return {
            "tool": "pdf_parser",
            "status": "success",
            "result": f"Extracted {150} pages from {file_path}",
            "artifact_uri": f"minio://artifacts/pdf_text_{hash(file_path) % 10000}.txt",
            "metadata": {"pages": 150, "text_length": 45000}
        }
    
    @staticmethod
    def vector_search(params: dict) -> dict:
        query = params.get("query", "search query")
        return {
            "tool": "vector_search",
            "status": "success",
            "result": [
                {"id": "doc-1", "score": 0.95, "text": "Relevant passage 1"},
                {"id": "doc-2", "score": 0.89, "text": "Relevant passage 2"},
                {"id": "doc-3", "score": 0.82, "text": "Relevant passage 3"}
            ],
            "artifact_uri": f"minio://artifacts/search_{hash(query) % 10000}.json",
            "metadata": {"query": query, "total_results": 3}
        }
    
    @staticmethod
    def repo_reader(params: dict) -> dict:
        repo_url = params.get("repo_url", "https://github.com/example/repo")
        return {
            "tool": "repo_reader",
            "status": "success",
            "result": f"Analyzed repository: {repo_url}",
            "artifact_uri": f"minio://artifacts/repo_{hash(repo_url) % 10000}.json",
            "metadata": {"files_analyzed": 47, "lines_of_code": 12500}
        }
    
    @staticmethod
    def unit_test_runner(params: dict) -> dict:
        test_path = params.get("test_path", "tests/")
        return {
            "tool": "unit_test_runner",
            "status": "success",
            "result": "Tests passed: 45/50",
            "artifact_uri": f"minio://artifacts/test_results_{hash(test_path) % 10000}.xml",
            "metadata": {"passed": 45, "failed": 5, "coverage": 0.87}
        }
    
    @staticmethod
    def email_api(params: dict) -> dict:
        to = params.get("to", "user@example.com")
        subject = params.get("subject", "Email Subject")
        return {
            "tool": "email_api",
            "status": "success",
            "result": f"Email queued to {to}",
            "artifact_uri": f"minio://artifacts/email_{hash(to + subject) % 10000}.eml",
            "metadata": {"to": to, "subject": subject, "message_id": "msg-12345"}
        }
    
    @staticmethod
    def calendar_api(params: dict) -> dict:
        event_title = params.get("title", "Meeting")
        return {
            "tool": "calendar_api",
            "status": "success",
            "result": f"Event '{event_title}' created",
            "artifact_uri": f"minio://artifacts/calendar_{hash(event_title) % 10000}.ics",
            "metadata": {"event_id": "evt-67890", "attendees": 3}
        }
    
    @staticmethod
    def ppt_api(params: dict) -> dict:
        title = params.get("title", "Presentation")
        return {
            "tool": "ppt_api",
            "status": "success",
            "result": f"Created presentation: {title}",
            "artifact_uri": f"minio://artifacts/presentation_{hash(title) % 10000}.pptx",
            "metadata": {"slides": 12, "format": "pptx"}
        }
    
    @staticmethod
    def tts(params: dict) -> dict:
        text = params.get("text", "Hello world")
        return {
            "tool": "tts",
            "status": "success",
            "result": f"Generated speech for {len(text)} characters",
            "artifact_uri": f"minio://artifacts/speech_{hash(text) % 10000}.mp3",
            "metadata": {"duration_seconds": len(text) * 0.1, "voice": "en-US-neural"}
        }
    
    @staticmethod
    def asr(params: dict) -> dict:
        audio_file = params.get("audio_file", "recording.mp3")
        return {
            "tool": "asr",
            "status": "success",
            "result": "Transcribed: This is a sample transcription",
            "artifact_uri": f"minio://artifacts/transcript_{hash(audio_file) % 10000}.txt",
            "metadata": {"duration_seconds": 45, "confidence": 0.94}
        }


TOOL_REGISTRY = {
    "browser": ToolExecutor.browser,
    "pdf_parser": ToolExecutor.pdf_parser,
    "vector_search": ToolExecutor.vector_search,
    "repo_reader": ToolExecutor.repo_reader,
    "unit_test_runner": ToolExecutor.unit_test_runner,
    "email_api": ToolExecutor.email_api,
    "calendar_api": ToolExecutor.calendar_api,
    "ppt_api": ToolExecutor.ppt_api,
    "tts": ToolExecutor.tts,
    "asr": ToolExecutor.asr,
}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "executor"}


@app.get("/v1/tools")
async def list_tools():
    return {
        "tools": list(TOOL_REGISTRY.keys()),
        "total": len(TOOL_REGISTRY)
    }


@app.post("/v1/execute")
async def execute_step(request: ExecuteRequest):
    step = request.step
    tool = step.tool
    
    if not tool:
        return {
            "step_id": step.step_id,
            "status": "success",
            "result": {"message": "No tool specified, step completed"},
            "artifacts": []
        }
    
    if tool not in TOOL_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Tool {tool} not found")
    
    tool_func = TOOL_REGISTRY[tool]
    tool_result = tool_func(step.params)
    
    return {
        "step_id": step.step_id,
        "skill_id": step.skill_id,
        "status": "success",
        "result": tool_result,
        "artifacts": [tool_result.get("artifact_uri", "")]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8003"))
    uvicorn.run(app, host="0.0.0.0", port=port)
