"""
Etapa 6 — Geração do PDF profissional com ReportLab.

Compila os 30 roteiros em PDF com:
- Capa, índice, roteiros formatados, guia de câmera destacado.
"""

from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from utils import (
    OUTPUT_DIR,
    SCRIPTS_DIR,
    read_client_brief,
    read_json,
    setup_logging,
)

logger = setup_logging("04_generate_pdf")

# ── Cores ────────────────────────────────────────────────────────────
ACCENT = colors.HexColor("#E63946")
DARK = colors.HexColor("#1a1a1a")
GRAY = colors.HexColor("#666666")
LIGHT_GRAY = colors.HexColor("#F5F5F5")
LIGHT_RED = colors.HexColor("#FFF3F3")
LIGHT_YELLOW = colors.HexColor("#FFFBEA")
WHITE = colors.white


def build_styles():
    """Cria todos os estilos de parágrafo."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "CoverTitle", fontName="Helvetica-Bold", fontSize=28,
        textColor=DARK, alignment=TA_CENTER, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "CoverSub", fontName="Helvetica", fontSize=14,
        textColor=GRAY, alignment=TA_CENTER, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "CoverMeta", fontName="Helvetica", fontSize=11,
        textColor=GRAY, alignment=TA_CENTER, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "SectionTitle", fontName="Helvetica-Bold", fontSize=18,
        textColor=DARK, spaceAfter=10, spaceBefore=0,
    ))
    styles.add(ParagraphStyle(
        "ScriptNumber", fontName="Helvetica-Bold", fontSize=10,
        textColor=ACCENT, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "ScriptTitle", fontName="Helvetica-Bold", fontSize=16,
        textColor=DARK, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "MetaTag", fontName="Helvetica", fontSize=8.5,
        textColor=GRAY, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "HookLabel", fontName="Helvetica-Bold", fontSize=9.5,
        textColor=ACCENT, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "HookText", fontName="Helvetica-Bold", fontSize=13,
        textColor=DARK, spaceAfter=4, leading=18,
    ))
    styles.add(ParagraphStyle(
        "HookDetail", fontName="Helvetica", fontSize=9,
        textColor=colors.HexColor("#444444"), spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "BlockHeader", fontName="Helvetica-Bold", fontSize=10.5,
        textColor=ACCENT, spaceAfter=4, spaceBefore=6,
    ))
    styles.add(ParagraphStyle(
        "BlockScript", fontName="Helvetica", fontSize=11,
        textColor=DARK, alignment=TA_JUSTIFY, leading=16, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "CamLabel", fontName="Helvetica-Bold", fontSize=8,
        textColor=GRAY,
    ))
    styles.add(ParagraphStyle(
        "CamValue", fontName="Helvetica", fontSize=8,
        textColor=DARK,
    ))
    styles.add(ParagraphStyle(
        "CamTitle", fontName="Helvetica-Bold", fontSize=7.5,
        textColor=GRAY, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        "CTAText", fontName="Helvetica-Bold", fontSize=12.5,
        textColor=WHITE, spaceAfter=4, leading=17,
    ))
    styles.add(ParagraphStyle(
        "CTAType", fontName="Helvetica", fontSize=9,
        textColor=colors.HexColor("#bbbbbb"), spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        "CTALabel", fontName="Helvetica-Bold", fontSize=9,
        textColor=ACCENT, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "RefText", fontName="Helvetica", fontSize=8,
        textColor=GRAY, leading=11,
    ))
    styles.add(ParagraphStyle(
        "TOCEntry", fontName="Helvetica", fontSize=9.5,
        textColor=DARK, leading=16,
    ))
    styles.add(ParagraphStyle(
        "TOCNum", fontName="Helvetica-Bold", fontSize=9.5,
        textColor=ACCENT,
    ))

    return styles


def esc(text):
    """Escapa texto para ReportLab XML."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def footer(canvas, doc):
    """Rodapé com número de página."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY)
    canvas.drawCentredString(A4[0] / 2, 1.2 * cm, f"{doc.page}")
    canvas.restoreState()


def cover_page(canvas, doc):
    """Página de capa sem rodapé."""
    pass


def build_cover(brief, styles):
    """Elementos da capa."""
    elements = []
    elements.append(Spacer(1, 8 * cm))
    elements.append(Paragraph(esc(brief["client_name"]), styles["CoverTitle"]))
    elements.append(Spacer(1, 0.5 * cm))

    # Linha de destaque
    line_table = Table([[""]], colWidths=[3 * cm], rowHeights=[3 * mm])
    line_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
        ("LINEBELOW", (0, 0), (-1, -1), 0, WHITE),
    ]))
    elements.append(line_table)

    elements.append(Spacer(1, 0.8 * cm))
    elements.append(Paragraph("30 Roteiros de Vídeo Viral", styles["CoverSub"]))
    elements.append(Spacer(1, 2 * cm))
    elements.append(Paragraph(f"Nicho: {esc(brief['niche'])}", styles["CoverMeta"]))
    elements.append(Paragraph(datetime.now().strftime("%d/%m/%Y"), styles["CoverMeta"]))
    elements.append(NextPageTemplate("content"))
    elements.append(PageBreak())
    return elements


def build_toc(scripts, styles):
    """Página de índice."""
    elements = []
    elements.append(Paragraph("Índice", styles["SectionTitle"]))
    elements.append(Spacer(1, 0.3 * cm))

    for s in scripts:
        num = s.get("number", "?")
        title = esc(s.get("title", "Sem título"))
        fmt = esc(s.get("format", ""))
        obj = esc(s.get("objective", ""))
        text = (
            f'<font name="Helvetica-Bold" color="#E63946">{num:02d}</font>'
            f'&nbsp;&nbsp;{title}'
            f'&nbsp;&nbsp;<font size="8" color="#888888">({fmt} · {obj})</font>'
        )
        elements.append(Paragraph(text, styles["TOCEntry"]))

    elements.append(PageBreak())
    return elements


def build_camera_table(guide, styles):
    """Tabela do guia de câmera."""
    if not guide:
        return []

    labels = {
        "position": "Posição",
        "framing": "Enquadramento",
        "movement": "Movimento",
        "lighting": "Iluminação",
        "production_notes": "Produção",
    }

    rows = []
    for key, label in labels.items():
        val = guide.get(key, "")
        if val:
            rows.append([
                Paragraph(f"<b>{label}</b>", styles["CamLabel"]),
                Paragraph(esc(str(val)), styles["CamValue"]),
            ])

    if not rows:
        return []

    col_widths = [2.5 * cm, 12 * cm]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
    ]))

    # Wrapper com fundo
    wrapper = Table(
        [[Paragraph("GUIA DE CÂMERA", styles["CamTitle"])], [table]],
        colWidths=[14.8 * cm],
    )
    wrapper.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))

    return [Spacer(1, 3 * mm), wrapper]


def build_script_page(script, styles):
    """Elementos de um roteiro."""
    elements = []
    num = script.get("number", "?")
    title = esc(script.get("title", "Sem título"))
    fmt = esc(script.get("format", ""))
    duration = esc(script.get("estimated_duration", ""))
    objective = esc(script.get("objective", ""))

    # Header
    elements.append(Paragraph(f"ROTEIRO {num:02d}", styles["ScriptNumber"]))
    elements.append(Paragraph(title, styles["ScriptTitle"]))
    elements.append(Paragraph(
        f"{fmt} &nbsp;·&nbsp; {duration} &nbsp;·&nbsp; {objective}",
        styles["MetaTag"],
    ))
    elements.append(Spacer(1, 4 * mm))

    # Gancho
    hook = script.get("hook", {})
    hook_text = esc(hook.get("text", ""))
    hook_type = esc(hook.get("type", ""))
    hook_screen = hook.get("screen_text")
    hook_action = hook.get("action")

    hook_content = [
        [Paragraph("GANCHO — PRIMEIROS 3 SEGUNDOS", styles["HookLabel"])],
        [Paragraph(f'"{hook_text}"', styles["HookText"])],
    ]
    details = []
    if hook_type:
        details.append(f"Tipo: {hook_type}")
    if hook_screen and hook_screen != "null":
        details.append(f"Tela: {esc(str(hook_screen))}")
    if hook_action:
        details.append(f"Ação: {esc(str(hook_action))}")
    if details:
        hook_content.append([Paragraph(" · ".join(details), styles["HookDetail"])])

    hook_table = Table(hook_content, colWidths=[14.8 * cm])
    hook_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_RED),
        ("LINEBEFOREDECOR", (0, 0), (0, -1), 4, ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    elements.append(hook_table)
    elements.append(Spacer(1, 6 * mm))

    # Blocos do corpo
    body = script.get("body", [])
    for block in body:
        if not isinstance(block, dict):
            continue
        bnum = block.get("block_number", "")
        time_range = esc(block.get("time_range", ""))
        text = esc(block.get("script", ""))

        elements.append(Paragraph(
            f'<font color="#E63946"><b>Bloco {bnum}</b></font>'
            f'&nbsp;&nbsp;<font size="8" color="#888888">{time_range}</font>',
            styles["BlockHeader"],
        ))
        elements.append(Paragraph(text, styles["BlockScript"]))

        cam = block.get("camera_guide", {})
        elements.extend(build_camera_table(cam, styles))
        elements.append(Spacer(1, 3 * mm))

    # CTA
    cta = script.get("cta", {})
    cta_text = esc(cta.get("text", ""))
    cta_type = esc(cta.get("type", ""))

    cta_content = [
        [Paragraph("CTA FINAL", styles["CTALabel"])],
        [Paragraph(cta_text, styles["CTAText"])],
        [Paragraph(f"Tipo: {cta_type}", styles["CTAType"])],
    ]
    cta_table = Table(cta_content, colWidths=[14.8 * cm])
    cta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    elements.append(Spacer(1, 4 * mm))
    elements.append(cta_table)

    # Referência de padrão
    ref = esc(script.get("viral_pattern_reference", ""))
    if ref:
        ref_content = [[Paragraph(
            f'<font color="#E76F51"><b>Padrão viral aplicado:</b></font> {ref}',
            styles["RefText"],
        )]]
        ref_table = Table(ref_content, colWidths=[14.8 * cm])
        ref_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT_YELLOW),
            ("LINEBEFOREDECOR", (0, 0), (0, -1), 2, colors.HexColor("#F4A261")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(Spacer(1, 3 * mm))
        elements.append(ref_table)

    elements.append(PageBreak())
    return elements


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    brief = read_client_brief()
    scripts_path = SCRIPTS_DIR / "scripts_raw.json"

    if not scripts_path.exists():
        logger.error(f"Arquivo não encontrado: {scripts_path}")
        logger.error("Execute 03_generate_scripts.py primeiro.")
        return

    scripts = read_json(scripts_path)
    if not scripts:
        logger.error("Nenhum roteiro encontrado em scripts_raw.json")
        return

    logger.info(f"Gerando PDF com {len(scripts)} roteiros para {brief['client_name']}")

    styles = build_styles()

    # Filename
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in brief["client_name"])
    pdf_path = OUTPUT_DIR / f"{safe_name}_30_roteiros.pdf"

    # Document setup
    doc = BaseDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=2.5 * cm,
        rightMargin=2.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"{brief['client_name']} — 30 Roteiros Virais",
        author="Sistema de Roteiros Virais",
    )

    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id="main",
    )

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=frame, onPage=cover_page),
        PageTemplate(id="content", frames=frame, onPage=footer),
    ])

    # Build elements
    elements = []
    elements.extend(build_cover(brief, styles))
    elements.extend(build_toc(scripts, styles))

    for s in scripts:
        elements.extend(build_script_page(s, styles))

    # Generate
    doc.build(elements)

    size_mb = pdf_path.stat().st_size / (1024 * 1024)
    logger.info(f"PDF gerado: {pdf_path}")

    print("\n" + "=" * 60)
    print("PDF GERADO COM SUCESSO")
    print(f"Arquivo: {pdf_path}")
    print(f"Roteiros: {len(scripts)}")
    print(f"Tamanho: {size_mb:.1f} MB")
    print("=" * 60)


if __name__ == "__main__":
    main()
