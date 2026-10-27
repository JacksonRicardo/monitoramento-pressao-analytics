"""Geração do relatório em PDF com ReportLab."""
from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .exportacao_excel import INSTRUCOES, _clarear

CINZA = colors.HexColor("#BFBFBF")


def _estilos(cor):
    base = getSampleStyleSheet()
    return {
        "titulo": ParagraphStyle(
            "titulo", parent=base["Title"], textColor=colors.white, fontSize=18, leading=22, alignment=TA_CENTER
        ),
        "sub": ParagraphStyle("sub", parent=base["Normal"], fontSize=9, textColor=colors.HexColor("#595959")),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], textColor=cor, fontSize=13, spaceBefore=10, spaceAfter=6
        ),
        "normal": ParagraphStyle("normal", parent=base["Normal"], fontSize=9, leading=12),
        "celula": ParagraphStyle("celula", parent=base["Normal"], fontSize=8, leading=10),
        "card_valor": ParagraphStyle(
            "card_valor", parent=base["Normal"], fontSize=16, leading=19, alignment=TA_CENTER, textColor=cor
        ),
        "card_rotulo": ParagraphStyle(
            "card_rotulo", parent=base["Normal"], fontSize=7.5, alignment=TA_CENTER, textColor=colors.HexColor("#595959")
        ),
        "aviso": ParagraphStyle(
            "aviso", parent=base["Normal"], fontSize=7.5, textColor=colors.HexColor("#7F7F7F"), alignment=TA_CENTER
        ),
    }


def _grafico_evolucao(analise, largura):
    serie = analise["series"]
    n = len(serie["sistolica"])
    altura = 6.5 * cm
    d = Drawing(largura, altura)
    lc = HorizontalLineChart()
    lc.x, lc.y = 30, 30
    lc.width, lc.height = largura - 50, altura - 55
    dados = [serie["sistolica"], serie["diastolica"]]
    pulsos = serie["pulsacao"]
    tem_pulso = any(pulsos)
    if tem_pulso:
        # Valores ausentes viram None (o ReportLab ignora o ponto)
        dados.append([p if p else None for p in pulsos])
    lc.data = dados
    passo = max(1, n // 10)
    lc.categoryAxis.categoryNames = [
        rotulo.split(" ")[0][:5] if i % passo == 0 else "" for i, rotulo in enumerate(serie["labels"])
    ]
    lc.categoryAxis.labels.fontSize = 7
    lc.categoryAxis.labels.angle = 0
    minimo = min(min(serie["diastolica"]), min(p for p in pulsos if p) if tem_pulso else 999)
    lc.valueAxis.valueMin = max(0, (minimo // 10) * 10 - 10)
    lc.valueAxis.valueMax = (max(serie["sistolica"]) // 10) * 10 + 20
    lc.valueAxis.valueStep = 20
    lc.valueAxis.labels.fontSize = 7
    lc.valueAxis.visibleGrid = True
    lc.valueAxis.gridStrokeColor = colors.HexColor("#E5E5E5")
    cores = [colors.HexColor("#C0392B"), colors.HexColor("#2E86C1"), colors.HexColor("#27AE60")]
    for i, cor in enumerate(cores[: len(dados)]):
        lc.lines[i].strokeColor = cor
        lc.lines[i].strokeWidth = 1.8
    if tem_pulso:
        lc.lines[2].strokeDashArray = [3, 2]
        lc.lines[2].strokeWidth = 1
    d.add(lc)

    legenda = Legend()
    legenda.x, legenda.y = 35, altura - 8
    legenda.fontSize = 7.5
    legenda.alignment = "right"
    legenda.columnMaximum = 1
    legenda.dx, legenda.dy = 8, 8
    nomes = ["Sistólica", "Diastólica", "Pulsação"]
    legenda.colorNamePairs = list(zip(cores[: len(dados)], nomes[: len(dados)]))
    d.add(legenda)
    return d


def _grafico_periodos(analise, largura, cor):
    d = Drawing(largura, 5 * cm)
    bc = VerticalBarChart()
    bc.x, bc.y = 30, 25
    bc.width, bc.height = largura - 45, 5 * cm - 45
    bc.data = [
        [p["sistolica"] or 0 for p in analise["por_periodo"]],
        [p["diastolica"] or 0 for p in analise["por_periodo"]],
    ]
    bc.categoryAxis.categoryNames = [p["periodo"] for p in analise["por_periodo"]]
    bc.categoryAxis.labels.fontSize = 8
    bc.valueAxis.valueMin = 0
    bc.valueAxis.labels.fontSize = 7
    bc.bars[0].fillColor = colors.HexColor("#C0392B")
    bc.bars[1].fillColor = colors.HexColor("#2E86C1")
    bc.barLabelFormat = "%.0f"
    bc.barLabels.fontSize = 6.5
    bc.barLabels.nudge = 6
    d.add(bc)
    d.add(String(largura / 2, 5 * cm - 10, "Média por período", fontSize=9, textAnchor="middle", fillColor=cor))
    return d


def _grafico_faixas(analise, largura, cor):
    d = Drawing(largura, 5 * cm)
    itens = [f for f in analise["distribuicao"] if f["n"]]
    pie = Pie()
    pie.x, pie.y = 15, 15
    pie.width = pie.height = 5 * cm - 40
    pie.data = [f["n"] for f in itens]
    pie.labels = [f"{f['pct']:.0f}%" for f in itens]
    pie.simpleLabels = 1
    pie.slices.fontSize = 7
    pie.slices.strokeColor = colors.white
    for i, f in enumerate(itens):
        pie.slices[i].fillColor = colors.HexColor(f["hex"])
    d.add(pie)
    legenda = Legend()
    legenda.x, legenda.y = pie.x + pie.width + 20, 5 * cm - 30
    legenda.fontSize = 7.5
    legenda.colorNamePairs = [(colors.HexColor(f["hex"]), f"{f['rotulo']} ({f['n']})") for f in itens]
    d.add(legenda)
    d.add(String(largura / 2, 5 * cm - 10, "Faixas de referência", fontSize=9, textAnchor="middle", fillColor=cor))
    return d


def _tabela_simples(linhas, larguras, cor_clara):
    t = Table(linhas, colWidths=larguras, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), cor_clara),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, CINZA),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
            ]
        )
    )
    return t


def gerar_pdf(medicoes, analise: dict, opcoes: dict, usuario) -> bytes:
    cor = colors.HexColor("#" + opcoes["cor"])
    cor_clara = colors.HexColor("#" + _clarear(opcoes["cor"]))
    est = _estilos(cor)
    buffer = BytesIO()
    margem = 1.5 * cm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margem,
        rightMargin=margem,
        topMargin=margem,
        bottomMargin=margem,
        title=opcoes["titulo"],
        author=usuario.get_full_name() or usuario.username,
    )
    largura = A4[0] - 2 * margem
    gerado = timezone.localtime()

    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#7F7F7F"))
        canvas.drawString(margem, 0.8 * cm, f"Gerado em {gerado:%d/%m/%Y %H:%M} – Controle de Pressão Arterial")
        canvas.drawRightString(A4[0] - margem, 0.8 * cm, f"Página {documento.page}")
        canvas.setStrokeColor(cor)
        canvas.setLineWidth(0.6)
        canvas.line(margem, 1.1 * cm, A4[0] - margem, 1.1 * cm)
        canvas.restoreState()

    elementos = []

    # ---- Cabeçalho ----------------------------------------------------------
    cab = Table([[Paragraph(escape(opcoes["titulo"].upper()), est["titulo"])]], colWidths=[largura])
    cab.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), cor),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elementos += [cab, Spacer(1, 8)]

    perfil = getattr(usuario, "perfil", None)
    info = [f"<b>Paciente:</b> {escape(usuario.get_full_name() or usuario.username)}"]
    if perfil and perfil.idade is not None:
        info.append(f"<b>Idade:</b> {perfil.idade} anos")
    if perfil and perfil.medico_responsavel:
        info.append(f"<b>Profissional:</b> {escape(perfil.medico_responsavel)}")
    if not analise["vazio"]:
        info.append(f"<b>Período:</b> {analise['inicio']:%d/%m/%Y} a {analise['fim']:%d/%m/%Y}")
    if opcoes["periodo"]:
        info.append(f"<b>Filtro:</b> {opcoes['periodo']}")
    elementos.append(Paragraph(" &nbsp;|&nbsp; ".join(info), est["normal"]))
    if perfil and perfil.medicamentos:
        elementos.append(Paragraph(f"<b>Medicamentos:</b> {escape(perfil.medicamentos)}", est["normal"]))
    elementos.append(Spacer(1, 8))

    if analise["vazio"]:
        elementos.append(Paragraph("Nenhuma medição encontrada para os filtros selecionados.", est["normal"]))
        doc.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
        return buffer.getvalue()

    # ---- Cards de estatísticas ---------------------------------------------
    if opcoes["estatisticas"]:
        elementos.append(Paragraph("Estatísticas", est["h2"]))
        pul = analise["pulsacao"]["media"] if analise["pulsacao"] else "-"
        cards = [
            (f"{analise['sistolica']['media']}/{analise['diastolica']['media']}", "Média (mmHg)"),
            (str(pul), "Pulsação média (bpm)"),
            (analise["maximos"], "Máximos"),
            (analise["minimos"], "Mínimos"),
            (str(analise["total"]), "Medições"),
        ]
        t = Table(
            [[Paragraph(v, est["card_valor"]) for v, _ in cards], [Paragraph(r, est["card_rotulo"]) for _, r in cards]],
            colWidths=[largura / len(cards)] * len(cards),
        )
        t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.6, CINZA),
                    ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
                    ("LINEAFTER", (0, 0), (-2, -1), 0.4, CINZA),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBFBFB")),
                    ("TOPPADDING", (0, 0), (-1, 0), 8),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                ]
            )
        )
        elementos += [t, Spacer(1, 6)]

        detalhes = [
            ["Indicador", "Sistólica", "Diastólica", "Pulsação"],
            ["Média", analise["sistolica"]["media"], analise["diastolica"]["media"], pul],
            [
                "Mediana",
                analise["sistolica"]["mediana"],
                analise["diastolica"]["mediana"],
                analise["pulsacao"]["mediana"] if analise["pulsacao"] else "-",
            ],
            [
                "Desvio padrão",
                analise["sistolica"]["desvio"],
                analise["diastolica"]["desvio"],
                analise["pulsacao"]["desvio"] if analise["pulsacao"] else "-",
            ],
            [
                "Variabilidade (CV %)",
                analise["sistolica"]["cv"],
                analise["diastolica"]["cv"],
                analise["pulsacao"]["cv"] if analise["pulsacao"] else "-",
            ],
        ]
        extras = [
            ["Indicador", "Valor"],
            ["Dias com registro", f"{analise['dias_com_registro']} de {analise['dias_no_intervalo']}"],
            ["PAM média", f"{analise['pam']['media']} mmHg"],
            ["Pressão de pulso média", f"{analise['pressao_pulso']['media']} mmHg"],
            ["Leituras >= 140/90", str(analise["leituras_elevadas"])],
        ]
        if analise.get("tendencia"):
            tnd = analise["tendencia"]
            extras.append(["Tendência sist./diast.", f"{tnd['sistolica']:+} / {tnd['diastolica']:+} mmHg/sem"])
        if analise.get("meta"):
            mt = analise["meta"]
            extras.append([f"Dentro da meta {mt['sistolica']}/{mt['diastolica']}", f"{mt['pct']}%"])
        lado = Table(
            [
                [
                    _tabela_simples(detalhes, [3 * cm, 1.9 * cm, 1.9 * cm, 1.9 * cm], cor_clara),
                    _tabela_simples(extras, [4.2 * cm, 3.6 * cm], cor_clara),
                ]
            ],
            colWidths=[largura * 0.53, largura * 0.47],
        )
        lado.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        elementos.append(lado)

    # ---- Gráfico ------------------------------------------------------------
    if opcoes["grafico"]:
        elementos.append(
            KeepTogether([Paragraph("Evolução da pressão arterial", est["h2"]), _grafico_evolucao(analise, largura)])
        )

    # ---- Análise ------------------------------------------------------------
    if opcoes["analise"]:
        graficos = Table(
            [[_grafico_periodos(analise, largura / 2 - 6, cor), _grafico_faixas(analise, largura / 2 - 6, cor)]],
            colWidths=[largura / 2, largura / 2],
        )
        periodo_tab = [["Período", "Medições", "Sistólica", "Diastólica", "Pulsação"]] + [
            [p["periodo"], p["n"], p["sistolica"] or "-", p["diastolica"] or "-", p["pulsacao"] or "-"]
            for p in analise["por_periodo"]
        ]
        elementos.append(
            KeepTogether(
                [
                    Paragraph("Análise por período e faixas de referência", est["h2"]),
                    graficos,
                    Spacer(1, 4),
                    _tabela_simples(periodo_tab, [largura / 5] * 5, cor_clara),
                    Spacer(1, 3),
                    Paragraph(
                        "Faixas de referência baseadas nas Diretrizes Brasileiras de Hipertensão Arterial (2020), "
                        "apenas para fins informativos. Não constituem diagnóstico.",
                        est["aviso"],
                    ),
                ]
            )
        )

    # ---- Tabela de registros -----------------------------------------------
    elementos.append(Paragraph("Registro de medições", est["h2"]))
    cab_tabela = ["Data", "Hora", "Sist.", "Diast."]
    chaves = []
    mapa = {
        "pulsacao": "Pulso",
        "periodo": "Período",
        "pam": "PAM",
        "classificacao": "Faixa",
        "nota_profissional": "Nota do profissional",
        "observacoes": "Observações",
    }
    for chave in ("pulsacao", "periodo", "pam", "classificacao", "nota_profissional", "observacoes"):
        if chave in opcoes["colunas"]:
            cab_tabela.append(mapa[chave])
            chaves.append(chave)

    linhas = [cab_tabela]
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), cor),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, CINZA),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
    ]
    for i, m in enumerate(medicoes, start=1):
        linha = [m.data.strftime("%d/%m/%Y"), m.hora.strftime("%H:%M"), m.sistolica, m.diastolica]
        for chave in chaves:
            if chave == "classificacao":
                linha.append(m.classificacao["rotulo"])
            elif chave == "pam":
                linha.append(m.pressao_media_arterial)
            elif chave in ("nota_profissional", "observacoes"):
                linha.append(Paragraph(escape(getattr(m, chave) or ""), est["celula"]))
            else:
                linha.append(getattr(m, chave) or "-")
        linhas.append(linha)
        if opcoes["destacar"]:
            if m.sistolica >= 180 or m.diastolica >= 110:
                estilo += [
                    ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5B7B1")),
                    ("FONTNAME", (0, i), (-1, i), "Helvetica-Bold"),
                ]
            elif m.sistolica >= 140 or m.diastolica >= 90:
                estilo.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FDEBD0")))
        if "classificacao" in chaves:
            col = 4 + chaves.index("classificacao")
            estilo.append(("TEXTCOLOR", (col, i), (col, i), colors.HexColor(m.classificacao["hex"])))

    fixas = [2.1 * cm, 1.3 * cm, 1.2 * cm, 1.3 * cm]
    tamanhos = {"pulsacao": 1.2 * cm, "periodo": 1.6 * cm, "pam": 1.1 * cm, "classificacao": 2.4 * cm}
    larguras = fixas + [tamanhos.get(c, 0) for c in chaves]
    textos = [i for i, c in enumerate(chaves) if c in ("nota_profissional", "observacoes")]
    restante = largura - sum(larguras)
    for i in textos:
        larguras[4 + i] = restante / len(textos)
    if not textos:
        fator = largura / sum(larguras)
        larguras = [w * fator for w in larguras]
    tabela = Table(linhas, colWidths=larguras, repeatRows=1)
    tabela.setStyle(TableStyle(estilo))
    elementos.append(tabela)
    if opcoes["destacar"]:
        elementos.append(Spacer(1, 4))
        elementos.append(
            Paragraph(
                "<font backColor='#FDEBD0'>&nbsp;&nbsp;&nbsp;&nbsp;</font> Leituras >= 140/90 &nbsp;&nbsp; "
                "<font backColor='#F5B7B1'>&nbsp;&nbsp;&nbsp;&nbsp;</font> Leituras >= 180/110",
                est["aviso"],
            )
        )

    # ---- Instruções ---------------------------------------------------------
    if opcoes["instrucoes"]:
        elementos.append(PageBreak())
        for texto, negrito in INSTRUCOES:
            if not texto:
                elementos.append(Spacer(1, 6))
            elif negrito:
                elementos.append(Paragraph(texto, est["h2"]))
            else:
                elementos.append(Paragraph(texto.strip(), est["normal"]))

    elementos += [
        Spacer(1, 14),
        Paragraph(
            "Documento para organização pessoal, sem diagnóstico. Consulte sempre seu médico para orientações "
            "sobre sua pressão arterial.",
            est["aviso"],
        ),
    ]
    doc.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    return buffer.getvalue()
