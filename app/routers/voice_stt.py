import asyncio
import contextlib
import json
import os
import tempfile
import wave
from io import BytesIO
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx
import websockets
from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    Depends
)
from fastapi.responses import Response
from pydub import AudioSegment

import azure.cognitiveservices.speech as speechsdk
import threading

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.db.session import get_db
from app.db.models_project import Project

from app.auth.encryption_service import get_encryption_service, EncryptionService

router = APIRouter()

WHISPER_STREAM_BASE_URL = "ws://whisper.k8s.iism.kit.edu/analyze/ws"
KARAI_BASE_URL =        "https://karai.k8s.iism.kit.edu/transcribe"
SAMPLE_RATE = 16000
PASSTHROUGH_KEYS = ["translate", "language", "with_emotions", "auto_close"]
CHUNK_MS = 10_000
PARALLEL_REQUESTS = 6
HTTPX_TIMEOUT = httpx.Timeout(30.0, read=120.0, connect=10.0)


def _build_whisper_stream_url(extra: Optional[dict] = None) -> str:
    base = WHISPER_STREAM_BASE_URL
    params: Dict[str, str] = {}
    if extra:
        for k in PASSTHROUGH_KEYS:
            v = extra.get(k)
            if v is not None:
                params[k] = str(v)
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{urlencode(params)}"


async def _iter_wav_chunks(
    wav_path: str, frames_per_chunk: int = SAMPLE_RATE // 2
) -> AsyncGenerator[bytes, None]:
    with contextlib.closing(wave.open(wav_path, "rb")) as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        if sampwidth != 2:
            raise HTTPException(status_code=400, detail="Expects 16-bit PCM WAV (sampwidth=2).")
        if framerate != SAMPLE_RATE:
            raise HTTPException(
                status_code=400, detail=f"Expects {SAMPLE_RATE} Hz, file has {framerate} Hz."
            )
        if nchannels != 1:
            raise HTTPException(status_code=400, detail="Expects mono (1 channel).")
        while True:
            data = wf.readframes(frames_per_chunk)
            if not data:
                break
            yield data


async def _collect_upstream_messages(ws) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    try:
        async for message in ws:
            try:
                results.append(json.loads(message))
            except json.JSONDecodeError:
                results.append({"raw": message})
    except websockets.exceptions.ConnectionClosed:
        pass
    return results


def _norm_bool_flag(val: Optional[str], default: bool = False) -> str:
    if val is None:
        return "true" if default else "false"
    return "true" if str(val).lower() in ("1", "true", "yes", "on") else "false"


def _detect_format(filename: str, content_type: Optional[str]) -> str:
    if filename:
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if ext:
            return ext
    if content_type:
        mapping = {
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/webm": "webm",
            "audio/ogg": "ogg",
            "audio/x-flac": "flac",
            "audio/flac": "flac",
            "audio/mp4": "mp4",
            "audio/aac": "aac",
            "audio/3gpp": "3gp",
        }
        return mapping.get(content_type.lower(), "wav")
    return "wav"


def _chunk_audio(content: bytes, fmt: str, chunk_ms: int) -> List[bytes]:
    audio = AudioSegment.from_file(BytesIO(content), format=fmt)
    chunks: List[bytes] = []
    for start_ms in range(0, len(audio), chunk_ms):
        seg = audio[start_ms : start_ms + chunk_ms]
        buf = BytesIO()
        seg.export(buf, format="wav")
        chunks.append(buf.getvalue())
    return chunks


async def _post_chunk(
    client: httpx.AsyncClient,
    upstream_url: str,
    chunk_bytes: bytes,
    index: int,
    original_filename: Optional[str],
) -> Tuple[int, str]:
    files = {
        "file": (
            f"{os.path.splitext(original_filename or 'audio')[0]}_chunk{index:04d}.wav",
            chunk_bytes,
            "audio/wav",
        )
    }
    r = await client.post(upstream_url, files=files)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=f"Chunk {index} failed: {r.text}")
    return index, r.text


async def stream_with_whisper(client_ws: WebSocket):
    await client_ws.accept()

    qp = dict(client_ws.query_params)

    language = qp.get("language", "en")
    translate = _norm_bool_flag(qp.get("translate"), False)
    with_emotions = _norm_bool_flag(qp.get("with_emotions"), False)
    auto_close = _norm_bool_flag(qp.get("auto_close"), False)

    upstream_url = _build_whisper_stream_url(
        extra={
            "language": language,
            "translate": translate,
            "with_emotions": with_emotions,
            "auto_close": auto_close,
        }
    )

    upstream = None
    reader_task: Optional[asyncio.Task] = None

    async def start_upstream_if_needed():
        nonlocal upstream, reader_task
        if upstream is not None:
            return
        try:
            upstream_ws = await websockets.connect(upstream_url)
        except Exception as e:
            await client_ws.close(code=1011, reason=f"Upstream connect failed: {e.__class__.__name__}")
            raise
        upstream = upstream_ws

        async def forward_upstream_to_client():
            try:
                async for message in upstream_ws:
                    try:
                        json.loads(message)
                        await client_ws.send_text(message)
                    except Exception:
                        if isinstance(message, (bytes, bytearray)):
                            await client_ws.send_bytes(message)
                        else:
                            await client_ws.send_text(str(message))
            except Exception:
                pass
            finally:
                with contextlib.suppress(Exception):
                    await client_ws.close()

        reader_task = asyncio.create_task(forward_upstream_to_client())

    try:
        while True:
            msg = await client_ws.receive()
            if msg.get("bytes") is not None:
                await start_upstream_if_needed()
                await upstream.send(msg["bytes"])
                continue
            if msg.get("text") is not None:
                txt = msg["text"]
                if txt == "__END__":
                    if upstream is not None:
                        with contextlib.suppress(Exception):
                            await upstream.send(b"")
                elif txt in ("__PING__", "__KEEPALIVE__"):
                    pass
                else:
                    await start_upstream_if_needed()
                    await upstream.send(txt.encode("utf-8"))
                continue
    except WebSocketDisconnect:
        if upstream is not None:
            with contextlib.suppress(Exception):
                await upstream.send(b"")
                await upstream.close()
    except Exception:
        if upstream is not None:
            with contextlib.suppress(Exception):
                await upstream.close()
    finally:
        if reader_task:
            reader_task.cancel()
        with contextlib.suppress(Exception):
            await client_ws.close()


async def test_with_whisper():
    upstream_url = _build_whisper_stream_url(
        extra={
            "translate": "false",
            "language": "en",
            "with_emotions": "false",
            "auto_close": "true",
        }
    )
    silence_samples = int(SAMPLE_RATE * 0.02)
    silence = (b"\x00\x00") * silence_samples
    try:
        connect_timeout = 5
        async with asyncio.timeout(connect_timeout):
            async with websockets.connect(upstream_url) as ws:
                await ws.send(silence)
                await ws.send(b"")
                try:
                    async with asyncio.timeout(3):
                        await ws.recv()
                except Exception:
                    pass
        return {"ok": True}
    except asyncio.TimeoutError as e:
        print(e)
        raise HTTPException(
            status_code=503,
            detail=f"STT upstream timeout: {e.__class__.__name__}",
        )
    except websockets.InvalidStatusCode as e:
        print(e)
        raise HTTPException(
            status_code=502,
            detail=f"STT upstream rejected connection: {getattr(e, 'status_code', 'unknown')}",
        )
    except Exception as e:
        print(e)
        raise HTTPException(
            status_code=502,
            detail=f"STT upstream error: {e.__class__.__name__}: {e}",
        )


async def test_with_azure(stt_key: str, stt_endpoint):
    speech_config = _create_speech_config("en", stt_key, stt_endpoint)
    if not speech_config:
        return {"ok" : False}
    return {"ok": True}
    
async def transcribe_with_karai(file: UploadFile = File(...), language: str = Query("en")):
    base_url = KARAI_BASE_URL
    query = urlencode({"language": language})
    upstream_url = f"{base_url}?{query}"

    content = await file.read()
    try:
        fmt = _detect_format(file.filename or "", file.content_type)
        chunks = _chunk_audio(content, fmt, CHUNK_MS)
        if not chunks:
            raise HTTPException(status_code=400, detail="Empty audio after decoding.")

        sem = asyncio.Semaphore(PARALLEL_REQUESTS)
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:

            async def bounded_post(idx: int, chunk: bytes):
                async with sem:
                    return await _post_chunk(client, upstream_url, chunk, idx, file.filename)

            tasks = [bounded_post(i, chunk) for i, chunk in enumerate(chunks)]
            results = await asyncio.gather(*tasks)

        results.sort(key=lambda x: x[0])
        full_transcript = "".join(t for _, t in results)

        return Response(content=full_transcript, media_type="text/plain")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Transcription proxy failed: {e}")
    finally:
        await file.close()

def _create_speech_config(language: str, stt_key: str, stt_endpoint: str) -> speechsdk.SpeechConfig:

    if not stt_key or not stt_endpoint:
        raise RuntimeError("AZURE_SPEECH_KEY or AZURE_SPEECH_REGION invalid")
    
    #endpoint -> region
    clean_region = stt_endpoint.split("/")[2].split(".")[0]

    try:
        speech_config = speechsdk.SpeechConfig(
            subscription=stt_key,
            region=clean_region,
        )
    except Exception as e:
        print(e)
        return None        

    clean_language = language
    if (language == "en"):
        clean_language = "en-us"
    if (language == "de"):
        clean_language = "de-de"
    
    speech_config.speech_recognition_language = clean_language
    return speech_config

async def transcribe_with_azure(
    file: UploadFile = File(...),
    speech_config: speechsdk.SpeechConfig = None,
):
    content = await file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None,
            _recognize_file_blocking,
            tmp_path,
            speech_config,
        )
                
        return Response(content=text, media_type="text/plain")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        await file.close()


def _recognize_file_blocking(path: str, speech_config: speechsdk.SpeechConfig) -> str:
    
    audio_config = speechsdk.audio.AudioConfig(filename=path)

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )
    result = recognizer.recognize_once()
    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    elif result.reason == speechsdk.ResultReason.NoMatch:
        return ""
    else:
        raise RuntimeError(f"Azure Speech failed: {result.reason} - {result.cancellation_details}")

async def stream_with_azure(
    client_ws: WebSocket,
    stt_key: str,
    stt_endpoint: str,
):
    await client_ws.accept()

    qp = dict(client_ws.query_params)
    language = qp.get("language", "en")

    try:
        speech_config = _create_speech_config(language, stt_key, stt_endpoint)
    except Exception as e:
        await client_ws.close(code=1011, reason=f"Azure STT config failed: {e}")
        return

    stream_format = speechsdk.audio.AudioStreamFormat(
        samples_per_second=SAMPLE_RATE,
        bits_per_sample=16,
        channels=1,
    )
    audio_stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
    audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)

    recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
    )

    loop = asyncio.get_running_loop()
    stop_event = threading.Event()

    async def send_json(obj: dict):
        await client_ws.send_text(json.dumps(obj))

    def recognizing_cb(evt: speechsdk.SpeechRecognitionEventArgs):
        if evt.result.reason == speechsdk.ResultReason.RecognizingSpeech:
            text = evt.result.text
            if text:
                loop.call_soon_threadsafe(
                    asyncio.create_task,
                    send_json({"type": "partial", "text": text}),
                )

    def recognized_cb(evt: speechsdk.SpeechRecognitionEventArgs):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            text = evt.result.text
            if text:
                loop.call_soon_threadsafe(
                    asyncio.create_task,
                    send_json({"type": "final", "text": text}),
                )
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            pass

    def session_stopped_cb(evt):
        stop_event.set()

    def canceled_cb(evt):
        stop_event.set()

    recognizer.recognizing.connect(recognizing_cb)
    recognizer.recognized.connect(recognized_cb)
    recognizer.session_stopped.connect(session_stopped_cb)
    recognizer.canceled.connect(canceled_cb)

    def recognition_worker():
        try:
            recognizer.start_continuous_recognition()
            stop_event.wait()
        finally:
            recognizer.stop_continuous_recognition()

    worker = threading.Thread(target=recognition_worker, daemon=True)
    worker.start()

    try:
        while True:
            msg = await client_ws.receive()

            if msg.get("bytes") is not None:
                data = msg["bytes"]
                if data:
                    audio_stream.write(data)
                else:
                    audio_stream.close()
                    stop_event.set()
                    break

            elif msg.get("text") is not None:
                txt = msg["text"]
                if txt == "__END__":
                    audio_stream.close()
                    stop_event.set()
                    break
                elif txt in ("__PING__", "__KEEPALIVE__"):
                    continue
                else:
                    await client_ws.send_text(txt)

    except WebSocketDisconnect:
        audio_stream.close()
        stop_event.set()
    except Exception:
        audio_stream.close()
        stop_event.set()
        raise
    finally:
        with contextlib.suppress(Exception):
            await client_ws.close()


@router.websocket("/api/stream")
async def stream_proxy(
    client_ws: WebSocket,
    slug: str = Query(""),
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
    ):
    
    res = await db.execute(
        select(Project).where(Project.slug == slug)
    )
    proj = res.scalars().first()

    stt_key = enc.decrypt(proj.stt_key)
    stt_endpoint = proj.stt_endpoint

    #return await stream_with_whisper(client_ws)
    return await stream_with_azure(client_ws, stt_key, stt_endpoint)

@router.get("/api/stream/test")
async def stt_test(
    slug: str = Query(""),
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
):
    res = await db.execute(
        select(Project).where(Project.slug == slug)
    )
    proj = res.scalars().first()

    stt_key = enc.decrypt(proj.stt_key)
    stt_endpoint = proj.stt_endpoint

    #return await transcribe_with_karai(file, language)
    #return await test_with_whisper()
    
    return await test_with_azure(stt_key, stt_endpoint)

@router.post("/api/transcribe/proxy")
async def transcribe_proxy(
    file: UploadFile = File(...),
    language: str = Query("en"),
    slug: str = Query(""),
    db: AsyncSession = Depends(get_db),
    enc: EncryptionService = Depends(get_encryption_service),
):
    res = await db.execute(
        select(Project).where(Project.slug == slug)
    )
    proj = res.scalars().first()

    stt_key = enc.decrypt(proj.stt_key)
    stt_endpoint = proj.stt_endpoint
    speech_config = _create_speech_config(language, stt_key, stt_endpoint)
    return await transcribe_with_azure(file, speech_config)
    #return await transcribe_with_karai(file, language)
