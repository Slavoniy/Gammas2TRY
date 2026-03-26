import os
import re
import asyncio
import json
import logging
import smtplib
import ssl
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
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

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.timeweb.cloud")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")

DEFAULT_GENERATION_PARAMS = {
    "format": "presentation",
    "dimensions": "16x9",
    "textMode": "generate",
    "amount": "medium",
    "language": "ru",
    "exportAs": "pdf",
    "imageOptions": {"source": "aiGenerated", "model": "flux-2-klein"},
}


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


def send_download_email(email: str, download_url: str, product_name: str) -> None:
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <p>Здравствуйте!</p>
        <p>Ваша презентация <strong>"{product_name}"</strong> готова.</p>
        <p>Скачать можно по ссылке (действительна 24 часа):</p>
        <p>
            <a href="{download_url}"
               style="display:inline-block;padding:12px 24px;background:#4F46E5;color:#fff;
                      text-decoration:none;border-radius:6px;font-weight:bold;">
                СКАЧАТЬ ПРЕЗЕНТАЦИЮ
            </a>
        </p>
        <p>С уважением,<br>Команда сервиса</p>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Ваша презентация готова!"
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, email, msg.as_string())
        logger.info("Email sent to %s for product '%s'", email, product_name)
    except Exception:
        logger.error("Failed to send email to %s", email, exc_info=True)


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


async def poll_and_notify(generation_id: str, email: str, product_name: str) -> None:
    for attempt in range(60):
        await asyncio.sleep(5)
        logger.debug("Polling generation id=%s, attempt=%d", generation_id, attempt + 1)

        if MOCK_MODE:
            import random
            if random.random() < 0.3:
                mock_url = f"https://mock-download.example.com/{generation_id}.pdf"
                logger.info(
                    "Generation completed (mock), id=%s, emailing %s", generation_id, email
                )
                await asyncio.to_thread(
                    send_download_email, email, mock_url, product_name
                )
                return
            continue

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{GAMMA_BASE_URL}/generations/{generation_id}",
                    headers=get_headers(),
                )
                response.raise_for_status()
                data = response.json()

            status = data.get("status")
            logger.debug("Generation id=%s status=%s", generation_id, status)

            if status == "completed":
                download_url = data.get("exportUrl") or data.get("export_url")
                if not download_url:
                    export_links = data.get("exportLinks", {})
                    download_url = export_links.get("pdf") or export_links.get("pptx")
                logger.info(
                    "Generation completed, id=%s, email sent to %s", generation_id, email
                )
                await asyncio.to_thread(
                    send_download_email, email, download_url or "", product_name
                )
                return
            elif status in ("failed", "cancelled", "error"):
                logger.error(
                    "Generation id=%s failed with status=%s", generation_id, status
                )
                return
        except Exception:
            logger.error("Error polling generation id=%s", generation_id, exc_info=True)

    logger.error("Generation timed out after 60 attempts, id=%s", generation_id)


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
        await poll_and_notify(generation_id, email, product_name)
        return

    payload = {
        "format": format_,
        "exportAs": DEFAULT_GENERATION_PARAMS["exportAs"],
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
        await poll_and_notify(generation_id, email, product_name)

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
        format_ = map_format(data.get("format", "presentation"))
        dimensions = map_dimensions(
            data.get("cardOptions_dimensions") or data.get("cardOptions.dimensions") or "16:9"
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


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
