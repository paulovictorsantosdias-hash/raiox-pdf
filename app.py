import os
import textwrap
from typing import Dict, List

from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from PIL import Image

app = FastAPI(title="Raio-X PDF")

# ===============================
# CONFIG
# ===============================
OUTPUT_DIR = "output"
LOGO_PATH = "logo_raiox.png"

PAGE_W, PAGE_H = A4

MARGIN_LEFT = 1.0 * cm
MARGIN_RIGHT = 1.0 * cm

# Cabeçalho
LOGO_WIDTH_CM = 5.6
LOGO_HEIGHT_CM = 2.4
LOGO_TOP_MARGIN_CM = 0.18
LOGO_GAP_CM = 0.22

HEADER_LINE_Y = PAGE_H - (
    (LOGO_TOP_MARGIN_CM + LOGO_HEIGHT_CM + LOGO_GAP_CM) * cm
)
HEADER_TEXT_Y = HEADER_LINE_Y - 0.42 * cm

# Conteúdo
CONTENT_TOP_Y = HEADER_TEXT_Y - 0.9 * cm
CONTENT_BOTTOM_Y = 2.1 * cm

# Rodapé
FOOTER_LINE_Y = 1.55 * cm
FOOTER_TEXT_Y = 1.0 * cm

# Fontes
FONT_HEADER = "Helvetica"
FONT_HEADER_BOLD = "Helvetica-Bold"
FONT_BODY = "Helvetica"
FONT_BODY_BOLD = "Helvetica-Bold"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ===============================
# MODELS
# ===============================
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


# ===============================
# HELPERS
# ===============================
def sanitize_filename(text: str) -> str:
    allowed = []
    for ch in text.lower().strip():
        if ch.isalnum():
            allowed.append(ch)
        elif ch in (" ", "-", "_"):
            allowed.append("_")
    return "".join(allowed).strip("_") or "arquivo"


def wrap_text(text: str, width_chars: int):
    return textwrap.wrap(
        text,
        width=width_chars,
        break_long_words=False,
        break_on_hyphens=False
    )


def get_logo():
    if os.path.exists(LOGO_PATH):
        return LOGO_PATH
    return None


# ===============================
# HEADER
# ===============================
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
    pdf.drawString(MARGIN_LEFT, HEADER_TEXT_Y, concurso)
    pdf.drawRightString(MARGIN_RIGHT * -1 + PAGE_W, HEADER_TEXT_Y, banca)


# ===============================
# FOOTER
# ===============================
def draw_footer(pdf: canvas.Canvas, concurso: str, pagina: int):
    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(0.7)
    pdf.line(MARGIN_LEFT, FOOTER_LINE_Y, PAGE_W - MARGIN_RIGHT, FOOTER_LINE_Y)

    pdf.setFont(FONT_HEADER, 8.5)
    pdf.drawString(MARGIN_LEFT, FOOTER_TEXT_Y, concurso)
    pdf.drawRightString(PAGE_W - MARGIN_RIGHT, FOOTER_TEXT_Y, f"Página {pagina}")


# ===============================
# PDF
# ===============================
def gerar_pdf(data: SimuladoRequest) -> str:
    filename = f"{sanitize_filename(data.concurso)}.pdf"
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
            pdf.drawString(MARGIN_LEFT, y, q.disciplina.upper())
            y -= 18
            disciplina_atual = q.disciplina

        pdf.setFont(FONT_BODY_BOLD, 10)
        pdf.drawString(
            MARGIN_LEFT,
            y,
            f"{i} - ({data.banca} – {data.concurso})"
        )
        y -= 14

        pdf.setFont(FONT_BODY, 8)
        pdf.setFillColor(colors.HexColor("#444444"))
        pdf.drawString(MARGIN_LEFT, y, f"[Origem: {q.origem}]")
        pdf.setFillColor(colors.black)
        y -= 12

        pdf.setFont(FONT_BODY, 9)

        for linha in wrap_text(q.texto, 95):
            pdf.drawString(MARGIN_LEFT, y, linha)
            y -= 12

        y -= 4

        for letra in ["A", "B", "C", "D", "E"]:
            if letra in q.alternativas:
                txt = f"({letra}) {q.alternativas[letra]}"
                for linha in wrap_text(txt, 92):
                    pdf.drawString(MARGIN_LEFT, y, linha)
                    y -= 11

        y -= 10

    # ===============================
    # GABARITO FINAL
    # ===============================
    nova_pagina()
    y = CONTENT_TOP_Y

    pdf.setFont(FONT_BODY_BOLD, 13)
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


# ===============================
# ROTAS
# ===============================
@app.get("/")
def root():
    return {"status": "online"}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate-pdf")
def generate_pdf(data: SimuladoRequest):
    arquivo = gerar_pdf(data)
    return FileResponse(
        arquivo,
        media_type="application/pdf",
        filename=os.path.basename(arquivo)
    )
