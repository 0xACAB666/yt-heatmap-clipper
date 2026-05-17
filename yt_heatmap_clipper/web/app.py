from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from ..capabilities import CapabilityReport, detect_capabilities
from ..config import WHISPER_MODEL
from ..engine import run_clip_job
from ..models import ClipJobRequest, ClipJobResult, CropMode, ProgressEvent
from ..youtube import extract_video_id


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
WEB_OUTPUT_ROOT = Path("clips") / "web"
WEB_WORK_ROOT = Path(".web-work")
CROP_MODES: tuple[CropMode, ...] = ("default", "split_left", "split_right")


@dataclass
class DashboardJob:
    id: str
    request: ClipJobRequest
    created_at: datetime
    status: str = "queued"
    latest_event: ProgressEvent = field(default_factory=lambda: ProgressEvent("queued"))
    result: ClipJobResult | None = None
    error: str | None = None

    @property
    def output_dir(self) -> Path:
        if self.request.output_dir is None:
            raise RuntimeError("dashboard jobs require an output directory")
        return Path(self.request.output_dir)


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, DashboardJob] = {}
        self._lock = Lock()

    def create(self, request: ClipJobRequest, *, job_id: str | None = None) -> DashboardJob:
        job = DashboardJob(id=job_id or uuid4().hex, request=request, created_at=datetime.now(timezone.utc))
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> DashboardJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def recent(self) -> list[DashboardJob]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True)

    def update_event(self, job_id: str, event: ProgressEvent) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.latest_event = event
            job.status = event.type

    def complete(self, job_id: str, result: ClipJobResult) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.result = result
            job.status = "completed"
            job.latest_event = ProgressEvent("completed")

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.error = error
            job.status = "failed"


def create_app(registry: JobRegistry | None = None) -> FastAPI:
    app = FastAPI(title="yt-heatmap-clipper dashboard")
    app.state.registry = registry or JobRegistry()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    def landing(request: Request) -> HTMLResponse:
        capability_report = detect_capabilities(configured_model=WHISPER_MODEL)
        jobs = request.app.state.registry.recent()
        return HTMLResponse(_render_page(capability_report, jobs))

    @app.get("/favicon.ico")
    def favicon() -> HTMLResponse:
        return HTMLResponse(status_code=204)

    @app.post("/jobs")
    async def submit_job(request: Request) -> RedirectResponse:
        form = await request.form()
        video_id = extract_video_id(str(form.get("youtube_url", "")).strip())
        crop_mode = str(form.get("crop_mode", "default"))
        use_subtitle = form.get("use_subtitle") == "on"
        requested_model = str(form.get("requested_model", "")).strip() or None

        if video_id is None:
            raise HTTPException(status_code=422, detail="Invalid YouTube URL")
        if crop_mode not in CROP_MODES:
            raise HTTPException(status_code=422, detail="Invalid crop mode")

        job_id = uuid4().hex
        output_dir = WEB_OUTPUT_ROOT / job_id
        work_dir = WEB_WORK_ROOT / job_id
        clip_request = ClipJobRequest(
            video_id=video_id,
            crop_mode=crop_mode,
            use_subtitle=use_subtitle,
            requested_model=requested_model,
            output_dir=str(output_dir),
            work_dir=str(work_dir),
        )
        job = request.app.state.registry.create(clip_request, job_id=job_id)
        Thread(target=_run_job, args=(request.app.state.registry, job.id), daemon=True).start()
        return RedirectResponse(url=f"/jobs/{job.id}", status_code=303)

    @app.get("/jobs/{job_id}", response_class=HTMLResponse)
    def job_detail(job_id: str, request: Request) -> HTMLResponse:
        job = _get_job_or_404(request.app.state.registry, job_id)
        return HTMLResponse(_render_job_page(job))

    @app.get("/jobs/{job_id}/status")
    def job_status(job_id: str, request: Request) -> dict[str, Any]:
        job = _get_job_or_404(request.app.state.registry, job_id)
        return _serialize_job(job)

    @app.get("/jobs/{job_id}/clips/{filename}")
    def serve_clip(job_id: str, filename: str, request: Request) -> FileResponse:
        job = _get_job_or_404(request.app.state.registry, job_id)
        output_dir = job.output_dir.resolve()
        file_path = (job.output_dir / filename).resolve()
        if file_path.parent != output_dir or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Clip not found")
        return FileResponse(file_path, media_type="video/mp4", filename=filename)

    return app


def _run_job(registry: JobRegistry, job_id: str) -> None:
    job = _get_job_or_404(registry, job_id)
    try:
        result = run_clip_job(job.request, on_event=lambda event: registry.update_event(job_id, event))
    except Exception as error:
        registry.fail(job_id, str(error))
        return
    registry.complete(job_id, result)


def _get_job_or_404(registry: JobRegistry, job_id: str) -> DashboardJob:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _serialize_job(job: DashboardJob) -> dict[str, Any]:
    clips = []
    if job.output_dir.exists():
        clips = [path.name for path in sorted(job.output_dir.glob("*.mp4"))]
    return {
        "id": job.id,
        "status": job.status,
        "latest_event": asdict(job.latest_event),
        "result": asdict(job.result) if job.result is not None else None,
        "error": job.error,
        "clips": clips,
    }


def _render_page(capabilities: CapabilityReport, jobs: list[DashboardJob]) -> str:
    job_rows = "".join(
        f'<li><a href="/jobs/{escape(job.id, quote=True)}">{escape(job.request.video_id)}</a><span class="status-pill">{escape(job.status)}</span></li>'
        for job in jobs[:6]
    ) or '<li class="muted">No dashboard jobs yet.</li>'
    ffmpeg_label = "Ready for clipping" if capabilities.ffmpeg_available else "Missing — install before export"
    subtitle_label = (
        "Available for optional captions"
        if capabilities.subtitle_backend_available
        else "Optional backend not installed"
    )
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>yt-heatmap-clipper dashboard</title>
        <link rel="stylesheet" href="/static/dashboard.css">
      </head>
      <body>
        <main class="shell">
          <section class="hero panel">
            <p class="eyebrow">Local utility dashboard</p>
            <h1>Turn replay heat into clean vertical cuts.</h1>
            <p class="lede">Single-process control panel over the shared clipping engine. Submit a video, monitor each isolated browser job, and collect vertical-ready outputs without leaving the local workflow.</p>
          </section>

          <section class="grid">
            <form class="panel form" method="post" action="/jobs">
              <div class="section-heading">
                <p class="eyebrow">New job</p>
                <h2>Create clips</h2>
              </div>
              <label>YouTube URL<input name="youtube_url" type="url" required placeholder="https://www.youtube.com/watch?v=..."></label>
              <label>Crop mode<select name="crop_mode">
                <option value="default">Default center crop</option>
                <option value="split_left">Split left facecam</option>
                <option value="split_right">Split right facecam</option>
              </select></label>
              <label>Model override<input name="requested_model" type="text" placeholder="Optional, e.g. base"></label>
              <label class="toggle"><input name="use_subtitle" type="checkbox"><span>Add auto subtitles</span></label>
              <button type="submit">Start clipping</button>
            </form>

            <aside class="panel summary">
              <div class="section-heading">
                <p class="eyebrow">Environment</p>
                <h2>Runtime readiness</h2>
              </div>
              <dl>
                 <div><dt>FFmpeg</dt><dd>{escape(ffmpeg_label)}</dd></div>
                 <div><dt>Subtitle backend</dt><dd>{escape(subtitle_label)}</dd></div>
                 <div><dt>Acceleration path</dt><dd>{escape(capabilities.acceleration.device)} / {escape(capabilities.acceleration.compute_type)}</dd></div>
                 <div><dt>Why this path</dt><dd>{escape(capabilities.acceleration.reason)}</dd></div>
                 <div><dt>Default model</dt><dd>{escape(capabilities.whisper_model.name)}</dd></div>
                 <div><dt>Model selection</dt><dd>{escape(capabilities.whisper_model.reason)}</dd></div>
              </dl>
            </aside>
          </section>

          <section class="panel recent">
            <div><p class="eyebrow">Recent jobs</p><h2>Latest activity</h2></div>
            <ul>{job_rows}</ul>
          </section>
        </main>
      </body>
    </html>
    """


def _render_job_page(job: DashboardJob) -> str:
    data = _serialize_job(job)
    clips = "".join(
        f'<li><a href="/jobs/{escape(job.id, quote=True)}/clips/{escape(clip, quote=True)}">{escape(clip)}</a></li>' for clip in data["clips"]
    ) or '<li class="muted">Clips appear here when ready.</li>'
    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Job {escape(job.id)}</title>
        <link rel="stylesheet" href="/static/dashboard.css">
      </head>
      <body>
        <main class="shell">
          <section class="panel hero compact">
            <p class="eyebrow">Job {escape(job.id[:8])}</p>
            <h1>{escape(job.request.video_id)}</h1>
            <p class="lede">Live browser job status: <strong id="job-status">{escape(job.status)}</strong>. This page refreshes progress automatically while the shared engine works in the background.</p>
          </section>
          <section class="grid">
            <article class="panel summary">
              <div class="section-heading">
                <p class="eyebrow">Latest progress</p>
                <h2>Processing state</h2>
              </div>
              <dl>
                 <div><dt>Current event</dt><dd id="event-type">{escape(job.latest_event.type)}</dd></div>
                 <div><dt>Segments detected</dt><dd id="total-segments">{escape(str(job.latest_event.total_segments or '-'))}</dd></div>
                 <div><dt>Clip being processed</dt><dd id="clip-index">{escape(str(job.latest_event.clip_index or '-'))}</dd></div>
                 <div><dt>Completed clips</dt><dd id="success-count">{escape(str(job.result.success_count if job.result else '-'))}</dd></div>
              </dl>
            </article>
            <article class="panel recent">
              <div><p class="eyebrow">Outputs</p><h2>Generated clips</h2></div>
              <ul id="clip-list">{clips}</ul>
            </article>
          </section>
          <p><a class="backlink" href="/">Start another job</a></p>
        </main>
        <script>
          const terminalStates = new Set(["completed", "failed"]);
          const clipList = document.querySelector("#clip-list");

          function renderValue(value) {{
            return value ?? "-";
          }}

          function renderClips(clips) {{
            clipList.replaceChildren();
            if (clips.length === 0) {{
              const empty = document.createElement("li");
              empty.className = "muted";
              empty.textContent = "Clips appear here when ready.";
              clipList.append(empty);
              return;
            }}

            for (const clip of clips) {{
              const item = document.createElement("li");
              const link = document.createElement("a");
              link.href = `/jobs/{job.id}/clips/${{clip}}`;
              link.textContent = clip;
              item.append(link);
              clipList.append(item);
            }}
          }}

          async function refreshJob() {{
            const response = await fetch("/jobs/{job.id}/status");
            if (!response.ok) {{
              return;
            }}
            const job = await response.json();
            document.querySelector("#job-status").textContent = job.status;
            document.querySelector("#event-type").textContent = job.latest_event.type;
            document.querySelector("#total-segments").textContent = renderValue(job.latest_event.total_segments);
            document.querySelector("#clip-index").textContent = renderValue(job.latest_event.clip_index);
            document.querySelector("#success-count").textContent = renderValue(job.result?.success_count);
            renderClips(job.clips);
            if (terminalStates.has(job.status)) {{
              clearInterval(refreshTimer);
            }}
          }}

          const refreshTimer = setInterval(refreshJob, 1500);
          if (!terminalStates.has("{job.status}")) {{
            refreshJob();
          }}
        </script>
      </body>
    </html>
    """


app = create_app()
