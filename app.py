import os
import textwrap
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from PIL import Image

app = FastAPI()

OUTPUT_DIR = "output"
LOGO_PATH = "logo_raiox.png"

PAGE_W, PAGE_H = A4
MARGIN_LEFT = 1.0 * cm
MARGIN_RIGHT = 1.0 * cm
HEADER_LINE_Y = PAGE_H - 2.9 * cm
HEADER_TEXT_Y = PAGE_H - 3.35 * cm
FOOTER_LINE_Y = 1.7 * cm
FOOTER_TEXT_Y = 1.05 * cm
CONTENT_TOP_Y = PAGE_H - 4.2 * cm
CONTENT_BOTTOM_Y = 2.2 * cm

LOGO_WIDTH_CM = 5.46
LOGO_HEIGHT_CM = 2.5

FONT_HEADER = "Helvetica"
FONT_HEADER_BOLD = "Helvetica-Bold"
FONT_BODY = "Helvetica"
FONT_BODY_BOLD = "Helvetica-Bold"

os.makedirs(OUTPUT_DIR, exist_ok=True)


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
    instrucoes: List[str] = []
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
            break_on_hyphens=False,
        )
        lines.extend(wrapped if wrapped else [""])
    return lines


def get_logo_path():
    return LOGO_PATH if os.path.exists(LOGO_PATH) else None


def draw_header(pdf: canvas.Canvas, concurso: str, banca: str) -> None:
    logo_path = get_logo_path()
    if logo_path:
        try:
            img = Image.open(logo_path)
            iw, ih = img.size
            box_w = LOGO_WIDTH_CM * cm
            box_h = LOGO_HEIGHT_CM * cm
            scale = min(box_w / iw, box_h / ih)
            draw_w = iw * scale
            draw_h = ih * scale
            x = (PAGE_W - draw_w) / 2
            y = PAGE_H - 0.9 * cm - draw_h
            pdf.drawImage(
                logo_path,
                x,
                y,
                width=draw_w,
                height=draw_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(1)
    pdf.line(MARGIN_LEFT, HEADER_LINE_Y, PAGE_W - MARGIN_RIGHT, HEADER_LINE_Y)

    pdf.setFont(FONT_HEADER, 8.5)
    pdf.setFillColor(colors.black)
    pdf.drawString(MARGIN_LEFT, HEADER_TEXT_Y, concurso)
    pdf.drawRightString(PAGE_W - MARGIN_RIGHT, HEADER_TEXT_Y, banca)


def draw_footer(pdf: canvas.Canvas, concurso: str, page_num: int) -> None:
    pdf.setStrokeColor(colors.black)
    pdf.setLineWidth(0.7)
    pdf.line(MARGIN_LEFT, FOOTER_LINE_Y, PAGE_W - MARGIN_RIGHT, FOOTER_LINE_Y)
    pdf.setFont(FONT_HEADER, 8.5)
    pdf.setFillColor(colors.black)
    pdf.drawString(MARGIN_LEFT, FOOTER_TEXT_Y, concurso)
    pdf.drawRightString(PAGE_W - MARGIN_RIGHT, FOOTER_TEXT_Y, f"Página {page_num}")


def generate_pdf(data: SimuladoRequest) -> str:
    filename = (
        f"simulado_{sanitize_filename(data.concurso)}_{sanitize_filename(data.cargo)}.pdf"
    )
    output_path = os.path.join(OUTPUT_DIR, filename)
    pdf = canvas.Canvas(output_path, pagesize=A4)

    page_num = 1
    draw_header(pdf, data.concurso, data.banca)
    draw_footer(pdf, data.concurso, page_num)

    y = CONTENT_TOP_Y
    current_disciplina = None

    for i, q in enumerate(data.questoes, start=1):
        if y < CONTENT_BOTTOM_Y + 80:
            pdf.showPage()
            page_num += 1
            draw_header(pdf, data.concurso, data.banca)
            draw_footer(pdf, data.concurso, page_num)
            y = CONTENT_TOP_Y
            current_disciplina = None

        if q.disciplina != current_disciplina:
            pdf.setFont(FONT_BODY_BOLD, 11)
            pdf.drawString(MARGIN_LEFT, y, q.disciplina.upper())
            y -= 18
            current_disciplina = q.disciplina

        pdf.setFont(FONT_BODY_BOLD, 9.5)
        pdf.drawString(MARGIN_LEFT, y, f"{i} - ({data.banca} – {data.concurso})")
        y -= 14

        pdf.setFont(FONT_BODY, 7.5)
        pdf.setFillColor(colors.HexColor("#444444"))
        pdf.drawString(MARGIN_LEFT, y, f"[Origem: {q.origem}]")
        y -= 12

        pdf.setFillColor(colors.black)
        pdf.setFont(FONT_BODY, 9)
        for line in wrap_text(q.texto, 95):
            pdf.drawString(MARGIN_LEFT, y, line)
            y -= 11

        y -= 4

        for alt in ["A", "B", "C", "D", "E"]:
            if alt in q.alternativas:
                for line in wrap_text(f"({alt}) {q.alternativas[alt]}", 90):
                    pdf.drawString(MARGIN_LEFT, y, line)
                    y -= 11
        y -= 10

    pdf.showPage()
    page_num += 1
    draw_header(pdf, data.concurso, data.banca)
    draw_footer(pdf, data.concurso, page_num)

    y = CONTENT_TOP_Y
    pdf.setFont(FONT_BODY_BOLD, 12)
    pdf.drawString(MARGIN_LEFT, y, "GABARITO")
    y -= 20

    pdf.setFont(FONT_BODY, 10)
    for i, q in enumerate(data.questoes, start=1):
        pdf.drawString(MARGIN_LEFT, y, f"{i} - {q.gabarito}")
        y -= 12

    pdf.save()
    return output_path


@app.get("/")
def root():
    return {"status": "ok", "message": "API online"}


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/generate-pdf")
def generate_pdf_route(payload: SimuladoRequest):
    try:
        path = generate_pdf(payload)
        return FileResponse(
            path,
            media_type="application/pdf",
            filename=os.path.basename(path),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
