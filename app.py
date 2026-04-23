import os
import textwrap
import uuid
from typing import Dict, List

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from PIL import Image

app = FastAPI(title="Raio-X PDF")

OUTPUT_DIR = "pdfs"
LOGO_PATH = "logo_raiox.png"

os.makedirs(OUTPUT_DIR, exist_ok=True)
app.mount("/files", StaticFiles(directory=OUTPUT_DIR), name="files")

PAGE_W, PAGE_H = A4

MARGIN_LEFT = 1.0 * cm
MARGIN_RIGHT = 1.0 * cm

LOGO_WIDTH_CM = 5.6
LOGO_HEIGHT_CM = 2.4
LOGO_TOP_MARGIN_CM = 0.18
LOGO_GAP_CM = 0.22

HEADER_LINE_Y = PAGE_H - ((LOGO_TOP_MARGIN_CM + LOGO_HEIGHT_CM + LOGO_GAP_CM) * cm)
HEADER_TEXT_Y = HEADER_LINE_Y - 0.42 * cm

CONTENT_TOP_Y = HEADER_TEXT_Y - 0.9 * cm
CONTENT_BOTTOM_Y = 2.1 * cm

FOOTER_LINE_Y = 1.55 * cm
FOOTER_TEXT_Y = 1.0 * cm

FONT_HEADER = "Helvetica"
FONT_BODY = "Helvetica"
FONT_BODY_BOLD = "Helvetica-Bold"


class Question(BaseModel):
    disciplina: str
    numero: int
    origem: str
    texto: str
    alternativas: Dict[str, str]
    gabarito: str = Field(pattern="^[A-E]$")


class SimuladoRequest(BaseModel):
    concurso: str
    banca: str
    cargo: str
    tipo: str = "Simulado"
    questoes: List[Question]


def sanitize_filename(text: str) -> str:
    allowed = []
    for ch in text.lower().strip():
        if ch.isalnum():
            allowed.append(ch)
        elif ch in (" ", "-", "_"):
            allowed.append("_")
    name = "".join(allowed)
    while "__" in name:
        name = name.replace("__", "_")
    return name.strip("_") or "arquivo"


def wrap_text(text: str, width_chars: int) -> List[str]:
    if not text:
        return [""]
    lines = []
    for paragraph in str(text).split("\n"):
        wrapped = textwrap.wrap(
            paragraph,
            width=width_chars,
            break_long_words=False,
            break_on_hyphens=False
        )
        lines.extend(wrapped if wrapped else [""])
    return lines


def get_logo():
    return LOGO_PATH if os.path.exists(LOGO_PATH) else None


def draw_header(pdf: canvas.Canvas, concurso: str, banca: str):
    logo = get_logo()

    if logo:
        try:
            img = Image.open(logo)
            iw, ih = img.size

            box_w = LOGO_WIDTH_CM * cm
            box_h = LOGO_HEIGHT_CM * cm

            scale = min(box_w / iw, box_h / ih)
            draw_w = iw * scale
            draw_h = ih * scale

            x = (PAGE_W - draw_w) / 2
            y = PAGE_H - (LOGO_TOP_MARGIN_CM * cm) - draw_h

            pdf.drawImage(
                logo,
                x,
                y,
                width=draw_w,
                height=draw_h,
                preserveAspectRatio=True,
                mask="auto"
            )
        except Exception:
            pass

    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(0.8)
    pdf.line(MARGIN_LEFT, HEADER_LINE_Y, PAGE_W - MARGIN_RIGHT, HEADER_LINE_Y)

    pdf.setFont(FONT_HEADER, 8.5)
    pdf.setFillColor(colors.black)
    pdf.drawString(MARGIN_LEFT, HEADER_TEXT_Y, concurso)
    pdf.drawRightString(PAGE_W - MARGIN_RIGHT, HEADER_TEXT_Y, banca)


def draw_footer(pdf: canvas.Canvas, concurso: str, pagina: int):
    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(0.7)
    pdf.line(MARGIN_LEFT, FOOTER_LINE_Y, PAGE_W - MARGIN_RIGHT, FOOTER_LINE_Y)

    pdf.setFont(FONT_HEADER, 8.5)
    pdf.setFillColor(colors.black)
    pdf.drawString(MARGIN_LEFT, FOOTER_TEXT_Y, concurso)
    pdf.drawRightString(PAGE_W - MARGIN_RIGHT, FOOTER_TEXT_Y, f"Página {pagina}")


def gerar_pdf(data: SimuladoRequest) -> str:
    filename = (
        f"{sanitize_filename(data.concurso)}_"
        f"{sanitize_filename(data.cargo)}_"
        f"{uuid.uuid4().hex[:8]}.pdf"
    )
    path = os.path.join(OUTPUT_DIR, filename)

    pdf = canvas.Canvas(path, pagesize=A4)
    pagina = 1

    def nova_pagina():
        nonlocal pagina
        pdf.showPage()
        pagina += 1
        draw_header(pdf, data.concurso, data.banca)
        draw_footer(pdf, data.concurso, pagina)

    draw_header(pdf, data.concurso, data.banca)
    draw_footer(pdf, data.concurso, pagina)

    y = CONTENT_TOP_Y
    disciplina_atual = None

    for i, q in enumerate(data.questoes, start=1):
        if y < CONTENT_BOTTOM_Y + 80:
            nova_pagina()
            y = CONTENT_TOP_Y
            disciplina_atual = None

        if q.disciplina != disciplina_atual:
            pdf.setFont(FONT_BODY_BOLD, 12)
            pdf.setFillColor(colors.black)
            pdf.drawString(MARGIN_LEFT, y, q.disciplina.upper())
            y -= 18
            disciplina_atual = q.disciplina

        pdf.setFont(FONT_BODY_BOLD, 10)
        pdf.setFillColor(colors.black)
        pdf.drawString(
            MARGIN_LEFT,
            y,
            f"{i} - ({data.banca} – {data.concurso})"
        )
        y -= 14

        pdf.setFont(FONT_BODY, 8)
        pdf.setFillColor(colors.HexColor("#444444"))
        pdf.drawString(MARGIN_LEFT, y, f"[Origem: {q.origem}]")
        y -= 12

        pdf.setFillColor(colors.black)
        pdf.setFont(FONT_BODY, 9)

        for linha in wrap_text(q.texto, 95):
            pdf.drawString(MARGIN_LEFT, y, linha)
            y -= 12

        y -= 4

        for letra in ["A", "B", "C", "D", "E"]:
            if letra in q.alternativas:
                texto_alt = f"({letra}) {q.alternativas[letra]}"
                for linha in wrap_text(texto_alt, 92):
                    pdf.drawString(MARGIN_LEFT, y, linha)
                    y -= 11

        y -= 10

    nova_pagina()
    y = CONTENT_TOP_Y

    pdf.setFont(FONT_BODY_BOLD, 13)
    pdf.setFillColor(colors.black)
    pdf.drawString(MARGIN_LEFT, y, "GABARITO")
    y -= 22

    pdf.setFont(FONT_BODY, 10)

    for i, q in enumerate(data.questoes, start=1):
        if y < CONTENT_BOTTOM_Y + 20:
            nova_pagina()
            y = CONTENT_TOP_Y
            pdf.setFont(FONT_BODY_BOLD, 13)
            pdf.drawString(MARGIN_LEFT, y, "GABARITO")
            y -= 22
            pdf.setFont(FONT_BODY, 10)

        pdf.drawString(MARGIN_LEFT, y, f"{i} - {q.gabarito}")
        y -= 12

    pdf.save()
    return path


@app.get("/")
def root():
    return {"status": "online"}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate-pdf")
def generate_pdf(data: SimuladoRequest):
    arquivo = gerar_pdf(data)
    nome_arquivo = os.path.basename(arquivo)

    return {
        "success": True,
        "filename": nome_arquivo,
        "download_url": f"https://raiox-pdf.onrender.com/files/{nome_arquivo}"
    }
