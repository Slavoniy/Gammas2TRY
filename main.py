import os
import re
import asyncio
import json
import logging
import subprocess
import tempfile
import uuid
import urllib.parse
from datetime import datetime
from typing import Optional

import boto3
import httpx
import requests
from botocore.client import Config
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app = FastAPI(title="Gamma API Proxy Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GAMMA_API_KEY = os.getenv("GAMMA_API_KEY")
GAMMA_BASE_URL = "https://public-api.gamma.app/v1.0"
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

TILDA_SECRET = os.getenv("TILDA_SECRET")

NOTISEND_API_KEY = os.getenv("NOTISEND_API_KEY", "")
NOTISEND_FROM_EMAIL = os.getenv("NOTISEND_FROM_EMAIL", "noreply@presentaciya.ru")
NOTISEND_FROM_NAME = os.getenv("NOTISEND_FROM_NAME", "presentaciya.ru")

S3_ENDPOINT   = os.getenv("S3_ENDPOINT", "https://s3.timeweb.cloud")
S3_BUCKET     = os.getenv("S3_BUCKET", "")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "")
S3_REGION     = os.getenv("S3_REGION", "ru-1")

BACKEND_URL = os.getenv("BACKEND_URL", "https://slavoniy-gammas2try-7fe3.twc1.net")

DEFAULT_GENERATION_PARAMS = {
    "format": "presentation",
    "dimensions": "16x9",
    "textMode": "generate",
    "amount": "medium",
    "language": "ru",
    "exportAs": "pdf",
    "imageOptions": {"source": "aiGenerated", "model": "flux-2-klein"},
}

DIMENSIONS_MAPPING = {
    # Презентации
    "презентация 16:9":               {"format": "presentation", "dim": "16x9"},
    "презентация 4:3":                {"format": "presentation", "dim": "4x3"},
    # Документ
    "документ а4":                    {"format": "document",     "dim": "a4"},
    # Соцсети
    "пост для соцсетей квадрат 1:1":  {"format": "social",       "dim": "1x1"},
    "пост для соцсетей истории 9:16": {"format": "social",       "dim": "9x16"},
    "пост для соцсетей портрет 4:5":  {"format": "social",       "dim": "4x5"},
    # Технические fallback
    "16:9":  {"format": "presentation", "dim": "16x9"},
    "4:3":   {"format": "presentation", "dim": "4x3"},
    "a4":    {"format": "document",     "dim": "a4"},
    "а4":    {"format": "document",     "dim": "a4"},
    "1x1":   {"format": "social",       "dim": "1x1"},
    "9x16":  {"format": "social",       "dim": "9x16"},
    "4x5":   {"format": "social",       "dim": "4x5"},
}

DEFAULT_FORMAT = {"format": "presentation", "dim": "16x9"}


def get_headers():
    return {
        "X-API-KEY": GAMMA_API_KEY,
        "Content-Type": "application/json",
    }


class GenerateRequest(BaseModel):
    # Mapping to Gamma API parameters
    format: str  # 'presentation', 'document', or 'webpage'
    dimensions: str  # '16x9', '4x3', 'a4'
    textMode: str  # 'generate', 'condense', 'preserve'
    inputText: str
    numCards: int = Field(ge=1, le=60)
    additionalInstructions: Optional[str] = Field(None, max_length=2000)
    amount: str  # 'brief', 'medium', 'detailed', 'extensive'
    tone: Optional[str] = None
    audience: Optional[str] = None
    language: str = "ru"
    themeId: Optional[str] = None
    exportAs: str  # 'pdf' or 'pptx'


def make_download_url(s3_url: str, filename: str) -> str:
    encoded_url  = urllib.parse.quote(s3_url, safe='')
    encoded_name = urllib.parse.quote(filename, safe='')
    return f"{BACKEND_URL}/download?url={encoded_url}&filename={encoded_name}"


def send_download_email(
    email: str,
    pdf_url: str,
    pptx_url: str,
    theme_name: str,
    num_cards: int,
) -> None:
    if not NOTISEND_API_KEY:
        logger.error("NOTISEND_API_KEY не задан — email не отправлен")
        return

    filename_base = make_filename(theme_name, num_cards)

    buttons = ""
    if pdf_url:
        buttons += f"""
        <a href="{pdf_url}"
           download="{filename_base}.pdf"
           target="_blank"
           style="display:inline-block;padding:14px 28px;background:#7C3AED;color:#fff;
                  text-decoration:none;border-radius:8px;font-size:16px;
                  font-weight:bold;margin:8px 8px 8px 0;">
            Скачать PDF →
        </a>"""
    if pptx_url:
        buttons += f"""
        <a href="{pptx_url}"
           download="{filename_base}.pptx"
           target="_blank"
           style="display:inline-block;padding:14px 28px;background:#06B6D4;color:#fff;
                  text-decoration:none;border-radius:8px;font-size:16px;
                  font-weight:bold;margin:8px 0;">
            Скачать PPTX →
        </a>"""

    links_fallback = ""
    if pdf_url:
        links_fallback += f'PDF: <a href="{pdf_url}" style="color:#7C3AED;">{pdf_url}</a><br>'
    if pptx_url:
        links_fallback += f'PPTX: <a href="{pptx_url}" style="color:#06B6D4;">{pptx_url}</a>'

    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:600px;
                 margin:0 auto;padding:20px;background:#f9f9f9;">
        <div style="background:white;padding:30px;border-radius:12px;">
            <h2 style="color:#7C3AED;margin-top:0;">
                Ваша презентация готова! 🎉
            </h2>
            <p style="color:#333;">
                Тема: <strong>{theme_name}</strong><br>
                Количество слайдов: <strong>{num_cards}</strong>
            </p>
            <p style="color:#333;">Скачайте файл по ссылке:</p>
            {buttons}
            <p style="color:#888;font-size:12px;margin-top:30px;
                      border-top:1px solid #eee;padding-top:20px;">
                С уважением, команда presentaciya.ru<br>
                Если кнопки не работают, скопируйте ссылки:<br>
                {links_fallback}
            </p>
        </div>
    </body>
    </html>
    """

    try:
        response = requests.post(
            "https://api.notisend.ru/v1/email/messages",
            headers={
                "Authorization": f"Bearer {NOTISEND_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "to": email,
                "from_email": NOTISEND_FROM_EMAIL,
                "from_name": NOTISEND_FROM_NAME,
                "subject": "Ваша презентация готова! 🎉",
                "html": html,
            },
            timeout=15,
        )

        if response.status_code in (200, 201, 202):
            msg_id = response.json().get("id", "unknown")
            logger.info("✅ Email отправлен через NotiSend: id=%s, to=%s", msg_id, email)
        else:
            logger.error(
                "❌ NotiSend ошибка: status=%s, body=%s",
                response.status_code, response.text,
            )

    except requests.RequestException as e:
        logger.error("❌ NotiSend HTTP ошибка: %s", e, exc_info=True)
    except Exception as e:
        logger.error("❌ NotiSend неизвестная ошибка: %s", e, exc_info=True)


def upload_to_s3(file_bytes: bytes, filename: str, content_type: str) -> str:
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name=S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=filename,
            Body=file_bytes,
            ContentType=content_type,
            ACL="public-read",
        )
        url = f"{S3_ENDPOINT}/{S3_BUCKET}/{filename}"
        logger.info("✅ Загружено в S3: %s", url)
        return url
    except Exception as e:
        logger.error("❌ Ошибка S3: %s", e, exc_info=True)
        return ""


def convert_pptx_to_pdf(pptx_bytes: bytes) -> Optional[bytes]:
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pptx_path = os.path.join(tmpdir, "presentation.pptx")
            pdf_path  = os.path.join(tmpdir, "presentation.pdf")
            with open(pptx_path, "wb") as f:
                f.write(pptx_bytes)
            result = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf",
                 "--outdir", tmpdir, pptx_path],
                capture_output=True, timeout=60,
            )
            if result.returncode != 0:
                logger.error("LibreOffice ошибка: %s", result.stderr.decode())
                return None
            with open(pdf_path, "rb") as f:
                return f.read()
    except subprocess.TimeoutExpired:
        logger.error("LibreOffice timeout при конвертации")
        return None
    except Exception as e:
        logger.error("Ошибка конвертации: %s", e, exc_info=True)
        return None


def transliterate(text: str) -> str:
    mapping = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo',
        'ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m',
        'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
        'ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch',
        'ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya',
        'А':'A','Б':'B','В':'V','Г':'G','Д':'D','Е':'E','Ё':'Yo',
        'Ж':'Zh','З':'Z','И':'I','Й':'Y','К':'K','Л':'L','М':'M',
        'Н':'N','О':'O','П':'P','Р':'R','С':'S','Т':'T','У':'U',
        'Ф':'F','Х':'Kh','Ц':'Ts','Ч':'Ch','Ш':'Sh','Щ':'Shch',
        'Ъ':'','Ы':'Y','Ь':'','Э':'E','Ю':'Yu','Я':'Ya',
    }
    result = ""
    for char in text:
        result += mapping.get(char, char)
    return result


def make_filename(theme_name: str, num_cards: int) -> str:
    clean = theme_name.replace("Презентация ", "").replace("для ", "dlya-")
    translit = transliterate(clean)
    safe = re.sub(r'[^a-zA-Z0-9\-]', '-', translit)
    safe = re.sub(r'-+', '-', safe).strip('-')[:40].strip('-')
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"{safe}_{num_cards}sl_{date_str}"


def extract_num_cards_from_options(options: list) -> int:
    for opt in options:
        variant = opt.get("variant", "")
        match = re.search(r"\d+", variant)
        if match:
            return int(match.group())
    return 10


def map_format(value: str) -> str:
    mapping = {
        "презентация": "presentation",
        "документ": "document",
        "пост для соцсетей": "webpage",
        "presentation": "presentation",
        "document": "document",
        "webpage": "webpage",
    }
    return mapping.get(value.lower().strip(), "presentation")


def map_text_mode(value: str) -> str:
    mapping = {
        "сгенерировать с нуля": "generate",
        "оставить только главное": "condense",
        "полностью сохранить": "preserve",
        "generate": "generate",
        "condense": "condense",
        "preserve": "preserve",
    }
    return mapping.get(value.lower().strip(), "generate")


def map_amount(value: str) -> str:
    mapping = {
        "краткий - больше визуализаций, меньше текста": "brief",
        "средний - дает баланс текста и дизайна": "medium",
        "подробный - более плотное заполнение слайда текстом": "detailed",
        "обширный - максимальное количество текста на каждой карточке": "extensive",
        "краткий": "brief",
        "средний": "medium",
        "подробный": "detailed",
        "обширный": "extensive",
        "brief": "brief",
        "medium": "medium",
        "detailed": "detailed",
        "extensive": "extensive",
    }
    return mapping.get(value.lower().strip(), "medium")


def map_language(value: str) -> str:
    mapping = {
        "русский": "ru", "английский": "en", "испанский": "es",
        "немецкий": "de", "французский": "fr", "итальянский": "it",
        "португальский": "pt", "китайский": "zh", "японский": "ja",
        "корейский": "ko", "арабский": "ar", "казахский": "kk",
        "сербский": "sr", "узбекский": "uz", "турецкий": "tr",
        "ru": "ru", "en": "en", "es": "es", "de": "de",
        "fr": "fr", "it": "it", "pt": "pt", "zh": "zh",
        "ja": "ja", "ko": "ko", "ar": "ar", "kk": "kk",
        "sr": "sr", "uz": "uz", "tr": "tr",
    }
    return mapping.get(value.lower().strip(), "ru")


def map_dimensions(value: str) -> str:
    mapping = {
        "16:9": "16x9", "16x9": "16x9",
        "4:3": "4x3", "4x3": "4x3",
        "а4": "a4", "a4": "a4",
        "квадрат 1:1": "16x9", "1x1": "16x9",
    }
    return mapping.get(value.lower().strip(), "16x9")


def parse_tilda_payment(body: dict) -> dict:
    """Parse Tilda's bracket-notation payment fields into a structured dict.

    Tilda sends form-urlencoded data with keys like:
      payment[products][0][name] = 'Презентация'
      payment[products][0][externalid] = 'sage'
      payment[products][0][options][0][variant] = '5 слайдов'
    """
    products: dict = {}
    for key, value in body.items():
        match = re.match(
            r'payment\[products\]\[(\d+)\]\[([^\]]+)\](?:\[(\d+)\]\[([^\]]+)\])?',
            key
        )
        if not match:
            continue
        prod_idx = int(match.group(1))
        field = match.group(2)
        opt_idx = match.group(3)
        opt_field = match.group(4)
        if prod_idx not in products:
            products[prod_idx] = {"options": {}}
        if opt_idx is not None:
            opt_idx = int(opt_idx)
            if opt_idx not in products[prod_idx]["options"]:
                products[prod_idx]["options"][opt_idx] = {}
            products[prod_idx]["options"][opt_idx][opt_field] = value
        else:
            if field != "options":
                products[prod_idx][field] = value
    result = []
    for idx in sorted(products.keys()):
        prod = products[idx]
        prod["options"] = [prod["options"][i] for i in sorted(prod["options"].keys())]
        result.append(prod)
    logger.info(f"Parsed payment products: {result}")
    return {"products": result}


async def poll_and_notify(generation_id: str, email: str, product_name: str, num_cards: int = 0) -> None:
    logger.info("Polling: id=%s, email=%s", generation_id, email)

    if MOCK_MODE:
        import random
        for _ in range(60):
            await asyncio.sleep(5)
            if random.random() < 0.3:
                mock_url = f"https://mock-download.example.com/{generation_id}.pptx"
                logger.info("Generation completed (mock), id=%s, emailing %s", generation_id, email)
                await asyncio.to_thread(
                    send_download_email, email, "", mock_url, product_name, num_cards
                )
                return
        logger.error("Generation timed out (mock), id=%s", generation_id)
        return

    # Poll Gamma API until completed
    gamma_url = None
    async with httpx.AsyncClient() as client:
        for attempt in range(1, 11):
            await asyncio.sleep(60)
            try:
                response = await client.get(
                    f"{GAMMA_BASE_URL}/generations/{generation_id}",
                    headers=get_headers(),
                )
                response.raise_for_status()
                data = response.json()
                status = data.get("status")
                logger.debug("attempt=%d, status=%s", attempt, status)
                if status == "completed":
                    gamma_url = (
                        data.get("exportUrl")
                        or data.get("export_url")
                        or data.get("exportLinks", {}).get("pptx")
                        or data.get("exportLinks", {}).get("pdf")
                    )
                    logger.info(
                        "Генерация завершена id=%s, ждём 30 сек перед скачиванием...",
                        generation_id,
                    )
                    await asyncio.sleep(30)
                    logger.info("Пауза завершена, скачиваем файл...")
                    break
                elif status in ("failed", "cancelled", "error"):
                    logger.error("Генерация провалилась: %s", status)
                    return
            except Exception as e:
                logger.error("Polling error attempt=%d: %s", attempt, e)

    if not gamma_url:
        logger.error("Нет ссылки после polling для %s", generation_id)
        return

    # Download PPTX from Gamma
    logger.info("Скачиваем PPTX: %s", gamma_url)
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(gamma_url, timeout=60)
            resp.raise_for_status()
            pptx_bytes = resp.content
            logger.info("PPTX скачан: %d байт", len(pptx_bytes))
        except Exception as e:
            logger.error("Ошибка скачивания PPTX: %s", e)
            return

    # Convert to PDF (blocking — run in thread)
    logger.info("Конвертируем PPTX → PDF...")
    pdf_bytes = await asyncio.to_thread(convert_pptx_to_pdf, pptx_bytes)

    # Upload both files to S3
    filename_base = make_filename(product_name, num_cards)
    folder_id = str(uuid.uuid4())[:8]
    pptx_s3_url = await asyncio.to_thread(
        upload_to_s3,
        pptx_bytes,
        f"presentations/{folder_id}/{filename_base}.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    pdf_s3_url = ""
    if pdf_bytes:
        pdf_s3_url = await asyncio.to_thread(
            upload_to_s3,
            pdf_bytes,
            f"presentations/{folder_id}/{filename_base}.pdf",
            "application/pdf",
        )
    else:
        logger.warning("PDF конвертация не удалась — отправляем только PPTX")

    # Wrap S3 URLs through backend download endpoint (forces browser download)
    pdf_download_url  = make_download_url(pdf_s3_url,  f"{filename_base}.pdf")  if pdf_s3_url  else ""
    pptx_download_url = make_download_url(pptx_s3_url, f"{filename_base}.pptx") if pptx_s3_url else ""

    await asyncio.to_thread(
        send_download_email, email, pdf_download_url, pptx_download_url, product_name, num_cards
    )


async def generate_and_notify(
    email: str,
    theme_id: Optional[str],
    product_name: str,
    num_cards: int,
    format_: str = "presentation",
    dimensions: str = "16x9",
    text_mode: str = "generate",
    language: str = "ru",
    amount: str = "medium",
    input_text: Optional[str] = None,
    additional: str = "",
    audience: str = "",
    tone: str = "",
) -> None:
    if not input_text:
        input_text = f"Создай презентацию на тему: {product_name}"

    if MOCK_MODE:
        generation_id = str(uuid.uuid4())
        logger.info("Generation started (mock), id=%s", generation_id)
        await poll_and_notify(generation_id, email, product_name, num_cards)
        return

    payload = {
        "format": format_,
        "exportAs": "pptx",
        "textMode": text_mode,
        "inputText": input_text,
        "numCards": num_cards,
        "textOptions": {
            "amount": amount,
            "language": language,
        },
        "imageOptions": DEFAULT_GENERATION_PARAMS["imageOptions"],
    }
    if format_ != "webpage":
        payload["cardOptions"] = {"dimensions": dimensions}
    if additional:
        payload["additionalInstructions"] = additional
    if tone:
        payload["textOptions"]["tone"] = tone
    if audience:
        payload["textOptions"]["audience"] = audience
    if theme_id:
        payload["themeId"] = theme_id

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GAMMA_BASE_URL}/generations",
                headers=get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        generation_id = data.get("generationId") or data.get("id")
        if not generation_id:
            logger.error("No generation ID returned from Gamma API for email=%s", email)
            return

        logger.info("Generation started, id=%s", generation_id)
        await poll_and_notify(generation_id, email, product_name, num_cards)

    except Exception:
        logger.error("Failed to start generation for email=%s", email, exc_info=True)


@app.get("/api/themes")
async def get_themes():
    if MOCK_MODE:
        return {
            "themes": [
                {"id": "theme1", "name": "Dark Elegance", "type": "standard"},
                {"id": "theme2", "name": "Light Corporate", "type": "standard"},
                {"id": "theme3", "name": "Playful Creative", "type": "custom"},
            ]
        }

    response = None
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{GAMMA_BASE_URL}/themes?limit=50", headers=get_headers()
            )
            response.raise_for_status()
            data = response.json()

            themes_list = (
                data.get("data", [])
                if isinstance(data, dict) and "data" in data
                else data
            )
            if not isinstance(themes_list, list):
                themes_list = []

            return {"themes": themes_list}
        except httpx.HTTPError as e:
            if response and response.status_code == 401:
                logger.warning("Failed to fetch themes from Gamma API: %s", e)
                return {
                    "themes": [
                        {"id": "theme1", "name": "Dark Elegance (Mock)", "type": "standard"},
                        {"id": "theme2", "name": "Light Corporate (Mock)", "type": "standard"},
                        {"id": "theme3", "name": "Playful Creative (Mock)", "type": "custom"},
                    ]
                }
            raise HTTPException(status_code=500, detail=f"Error fetching themes: {str(e)}")


@app.get("/api/generation/{generation_id}")
async def get_generation(generation_id: str):
    if MOCK_MODE:
        import random
        if random.random() < 0.3:
            return {
                "status": "completed",
                "downloadUrl": "https://mock-download.example.com/mock_file.pdf",
            }
        return {"status": "in_progress"}

    response = None
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{GAMMA_BASE_URL}/generations/{generation_id}", headers=get_headers()
            )
            response.raise_for_status()
            data = response.json()

            status = data.get("status")
            if status == "completed":
                download_url = data.get("exportUrl") or data.get("export_url")
                if not download_url:
                    export_links = data.get("exportLinks", {})
                    download_url = export_links.get("pdf") or export_links.get("pptx")
                return {"status": "completed", "downloadUrl": download_url}
            elif status in ("failed", "cancelled", "error"):
                raise HTTPException(
                    status_code=500, detail=f"Generation failed with status: {status}"
                )
            return {"status": status}

        except httpx.HTTPError as e:
            error_detail = str(e)
            x_request_id = "N/A"
            if response is not None:
                x_request_id = response.headers.get("x-request-id", "N/A")
                try:
                    error_detail = response.json()
                except ValueError:
                    error_detail = response.text
            raise HTTPException(
                status_code=500,
                detail=f"Error checking generation status: {error_detail} (x-request-id: {x_request_id})",
            )


@app.post("/api/generate")
async def generate_document(req: GenerateRequest):
    if MOCK_MODE:
        await asyncio.sleep(1)
        return {"generationId": str(uuid.uuid4())}

    payload = {
        "format": req.format,
        "exportAs": req.exportAs,
        "textMode": req.textMode,
        "inputText": req.inputText,
        "numCards": req.numCards,
        "textOptions": {
            "amount": req.amount,
            "language": req.language,
        },
        "imageOptions": {
            "source": "aiGenerated",
            "model": "flux-2-klein",
        },
    }

    if req.format != "webpage":
        payload["cardOptions"] = {"dimensions": req.dimensions}

    if req.additionalInstructions:
        payload["additionalInstructions"] = req.additionalInstructions
    if req.tone:
        payload["textOptions"]["tone"] = req.tone
    if req.audience:
        payload["textOptions"]["audience"] = req.audience
    if req.themeId:
        payload["themeId"] = req.themeId

    response = None
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{GAMMA_BASE_URL}/generations",
                headers=get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            generation_id = data.get("generationId", data.get("id"))

            if not generation_id:
                raise HTTPException(
                    status_code=500, detail="No generation ID returned from Gamma API."
                )

            return {"generationId": generation_id}

        except httpx.HTTPError as e:
            error_detail = str(e)
            x_request_id = "N/A"

            if response is not None:
                x_request_id = response.headers.get("x-request-id", "N/A")

                if response.status_code == 401:
                    raise HTTPException(
                        status_code=401,
                        detail="Недействительный или просроченный API-ключ Gamma",
                    )

                try:
                    raw_text = response.text
                    logger.error(
                        "Gamma API Error Response (x-request-id: %s): %s",
                        x_request_id,
                        raw_text,
                    )
                    try:
                        error_detail = response.json()
                    except ValueError:
                        error_detail = raw_text
                except Exception as ex:
                    logger.error("Failed to read error response: %s", ex)
            else:
                logger.error("Gamma API Request Failed without response: %s", e)

            raise HTTPException(
                status_code=500,
                detail=f"Gamma API Error: {error_detail} (x-request-id: {x_request_id})",
            )


@app.post("/webhook/tilda")
async def webhook_tilda(request: Request, background_tasks: BackgroundTasks):
    # 1. Read token from headers / query params (before body is consumed)
    header_token = (
        request.headers.get("X-Tilda-Secret")
        or request.headers.get("TILDA_SECRET")
        or request.query_params.get("secret")
    )

    # 2. Parse body: JSON or form-urlencoded
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        raw = form.get("data")
        if raw and isinstance(raw, str):
            data = json.loads(raw)
        else:
            data = dict(form)

    logger.info(f"Webhook body: {dict(data)}")

    # 3. Final token check: header OR body field
    if TILDA_SECRET:
        body_token = (
            data.get("TILDA_SECRET")
            or data.get("X-Tilda-Secret")
            or data.get("api_key")
            or data.get("secret")
        )
        token = header_token or body_token
        if not token or token != TILDA_SECRET:
            logger.warning(
                f"Webhook: неверный токен. "
                f"Header: {header_token}, Body keys: {list(data.keys())}"
            )
            return JSONResponse({"status": "forbidden"}, status_code=403)

    # Тильда шлёт тестовый ping при добавлении webhook — отвечаем 200
    has_payment = data.get("payment") or any(k.startswith("payment[") for k in data)
    if data.get("test") == "test" or (not data.get("email") and not data.get("Email") and not has_payment):
        logger.info("Webhook: получен тестовый запрос от Тильды, отвечаем 200 OK")
        return JSONResponse({"status": "ok", "message": "webhook connected"})

    try:
        # 4. Extract fields
        email = data.get("email") or data.get("Email") or ""

        # Tilda sends payment as bracket-notation keys (form-urlencoded)
        # Try nested dict first (JSON mode), fall back to bracket parsing
        raw_payment = data.get("payment")
        if isinstance(raw_payment, dict):
            payment = raw_payment
        else:
            payment = parse_tilda_payment(data)

        products = payment.get("products", [])
        if not products:
            logger.warning("No products in payment payload, using defaults")
            product: dict = {}
        else:
            product = products[0]

        theme_id = product.get("externalid")
        product_name = product.get("name", "Презентация")
        num_cards = extract_num_cards_from_options(product.get("options", []))

        # Map Tilda field values (Russian labels → Gamma API codes)
        # Tilda sends nested keys with underscores: cardOptions_dimensions
        dimensions_raw = (
            data.get("dimensions", "")
            or data.get("cardOptions_dimensions", "")
            or data.get("cardOptions.dimensions", "")
            or "презентация 16:9"
        ).lower().strip()
        format_map = DIMENSIONS_MAPPING.get(dimensions_raw, DEFAULT_FORMAT)
        format_    = format_map["format"]
        dimensions = format_map["dim"]
        logger.info(
            "Dimensions raw: '%s' → format=%s, dim=%s",
            dimensions_raw, format_, dimensions,
        )
        text_mode = map_text_mode(
            data.get("textMode") or data.get("textmode") or "generate"
        )
        language = map_language(
            data.get("textOptions_language") or data.get("textOptions.language") or "русский"
        )
        amount = map_amount(
            data.get("textOptions_amount") or data.get("textOptions.amount") or "medium"
        )
        input_text = data.get("inputText") or data.get("inputtext") or ""
        additional = data.get("additionalInstructions") or data.get("additionalinstructions") or ""
        audience = data.get("textOptions_audience") or data.get("textOptions.audience") or ""
        tone = data.get("textOptions_tone") or data.get("textOptions.tone") or ""

        logger.info(
            "Webhook: email=%s themeId=%s numCards=%d format=%s dimensions=%s "
            "textMode=%s language=%s amount=%s",
            email, theme_id, num_cards, format_, dimensions, text_mode, language, amount,
        )

        background_tasks.add_task(
            generate_and_notify,
            email, theme_id, product_name, num_cards,
            format_, dimensions, text_mode, language, amount, input_text, additional, audience, tone,
        )

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)


@app.get("/download")
async def download_file(url: str, filename: str):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=60, follow_redirects=True)
            resp.raise_for_status()

        if filename.endswith(".pdf"):
            content_type = "application/pdf"
        elif filename.endswith(".pptx"):
            content_type = (
                "application/vnd.openxmlformats-officedocument"
                ".presentationml.presentation"
            )
        else:
            content_type = "application/octet-stream"

        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        return StreamingResponse(
            iter([resp.content]),
            headers=headers,
            media_type=content_type,
        )
    except Exception as e:
        logger.error("Ошибка download endpoint: %s", e)
        raise HTTPException(status_code=500, detail="Ошибка скачивания файла")


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
