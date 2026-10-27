"""Análise de dados das medições de pressão arterial.

Utiliza apenas a biblioteca padrão (``statistics``) para manter o projeto leve.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Iterable

from .models import FAIXAS_REFERENCIA, Periodo

DIAS_SEMANA = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _resumo(valores: list[float]) -> dict | None:
    valores = [v for v in valores if v is not None]
    if not valores:
        return None
    media = statistics.fmean(valores)
    desvio = statistics.stdev(valores) if len(valores) > 1 else 0.0
    return {
        "media": round(media),
        "media_exata": round(media, 1),
        "mediana": round(statistics.median(valores)),
        "desvio": round(desvio, 1),
        "cv": round(desvio / media * 100, 1) if media else 0.0,
        "minimo": min(valores),
        "maximo": max(valores),
        "n": len(valores),
    }


def _media(valores: Iterable) -> float | None:
    valores = [v for v in valores if v is not None]
    return round(statistics.fmean(valores), 1) if valores else None


def _tendencia(medicoes: list) -> dict | None:
    """Regressão linear (mmHg por semana) da sistólica e diastólica ao longo do tempo."""
    if len(medicoes) < 3:
        return None
    base = medicoes[0].data
    xs = [(m.data - base).days + m.hora.hour / 24 for m in medicoes]
    if len(set(xs)) < 2:
        return None
    try:
        sis = statistics.linear_regression(xs, [m.sistolica for m in medicoes]).slope * 7
        dia = statistics.linear_regression(xs, [m.diastolica for m in medicoes]).slope * 7
    except statistics.StatisticsError:
        return None

    def _rotulo(valor):
        if valor > 0.5:
            return "alta"
        if valor < -0.5:
            return "queda"
        return "estável"

    return {
        "sistolica": round(sis, 1),
        "diastolica": round(dia, 1),
        "sistolica_rotulo": _rotulo(sis),
        "diastolica_rotulo": _rotulo(dia),
    }


def _media_movel(valores: list[int], janela: int = 7) -> list[float | None]:
    resultado: list[float | None] = []
    for i in range(len(valores)):
        if i + 1 < janela:
            resultado.append(None)
        else:
            resultado.append(round(statistics.fmean(valores[i + 1 - janela : i + 1]), 1))
    return resultado


def analisar(queryset, perfil=None) -> dict:
    """Gera todas as métricas utilizadas no dashboard, na planilha e no PDF."""
    medicoes = sorted(queryset, key=lambda m: (m.data, m.hora))
    total = len(medicoes)
    resultado: dict = {"total": total, "vazio": total == 0}
    if not medicoes:
        return resultado

    sis = [m.sistolica for m in medicoes]
    dia = [m.diastolica for m in medicoes]
    pul = [m.pulsacao for m in medicoes if m.pulsacao]
    pam = [m.pressao_media_arterial for m in medicoes]
    pp = [m.pressao_pulso for m in medicoes]

    resultado.update(
        {
            "inicio": medicoes[0].data,
            "fim": medicoes[-1].data,
            "dias_com_registro": len({m.data for m in medicoes}),
            "dias_no_intervalo": (medicoes[-1].data - medicoes[0].data).days + 1,
            "sistolica": _resumo(sis),
            "diastolica": _resumo(dia),
            "pulsacao": _resumo(pul),
            "pam": _resumo(pam),
            "pressao_pulso": _resumo(pp),
            # Igual à planilha original: máximos e mínimos podem vir de medições diferentes
            "maximos": f"{max(sis)} / {max(dia)}",
            "minimos": f"{min(sis)} / {min(dia)}",
            "tendencia": _tendencia(medicoes),
            "ultima": medicoes[-1],
        }
    )
    resultado["regularidade"] = round(
        resultado["dias_com_registro"] / resultado["dias_no_intervalo"] * 100
    )

    # ---- Por período do dia -------------------------------------------------
    por_periodo = []
    for valor, rotulo in Periodo.choices:
        grupo = [m for m in medicoes if m.periodo == valor]
        por_periodo.append(
            {
                "periodo": rotulo,
                "n": len(grupo),
                "sistolica": _media(m.sistolica for m in grupo),
                "diastolica": _media(m.diastolica for m in grupo),
                "pulsacao": _media(m.pulsacao for m in grupo),
            }
        )
    resultado["por_periodo"] = por_periodo

    # ---- Por dia da semana --------------------------------------------------
    semana = defaultdict(list)
    for m in medicoes:
        semana[m.data.weekday()].append(m)
    resultado["por_dia_semana"] = [
        {
            "dia": DIAS_SEMANA[i],
            "n": len(semana[i]),
            "sistolica": _media(m.sistolica for m in semana[i]),
            "diastolica": _media(m.diastolica for m in semana[i]),
        }
        for i in range(7)
    ]

    # ---- Distribuição por faixa de referência ------------------------------
    contagem = Counter(m.classificacao["chave"] for m in medicoes)
    resultado["distribuicao"] = [
        {
            "chave": chave,
            "rotulo": rotulo,
            "cor": cor,
            "hex": hexa,
            "n": contagem.get(chave, 0),
            "pct": round(contagem.get(chave, 0) / total * 100, 1),
        }
        for chave, rotulo, _, _, cor, hexa in FAIXAS_REFERENCIA
    ]
    resultado["leituras_elevadas"] = sum(
        1 for m in medicoes if m.sistolica >= 140 or m.diastolica >= 90
    )
    resultado["leituras_muito_altas"] = sum(
        1 for m in medicoes if m.sistolica >= 180 or m.diastolica >= 110
    )

    # ---- Meta definida pelo profissional -----------------------------------
    if perfil is not None and perfil.tem_meta:
        dentro = sum(
            1 for m in medicoes if m.sistolica <= perfil.meta_sistolica and m.diastolica <= perfil.meta_diastolica
        )
        resultado["meta"] = {
            "sistolica": perfil.meta_sistolica,
            "diastolica": perfil.meta_diastolica,
            "dentro": dentro,
            "pct": round(dentro / total * 100, 1),
        }

    # ---- Comparativo: últimos 30 dias x 30 dias anteriores -----------------
    ref = medicoes[-1].data
    atual = [m for m in medicoes if ref - timedelta(days=30) < m.data <= ref]
    anterior = [m for m in medicoes if ref - timedelta(days=60) < m.data <= ref - timedelta(days=30)]
    if atual and anterior:
        a_sis, b_sis = _media(m.sistolica for m in atual), _media(m.sistolica for m in anterior)
        a_dia, b_dia = _media(m.diastolica for m in atual), _media(m.diastolica for m in anterior)
        resultado["comparativo"] = {
            "atual_sis": a_sis,
            "anterior_sis": b_sis,
            "delta_sis": round(a_sis - b_sis, 1),
            "atual_dia": a_dia,
            "anterior_dia": b_dia,
            "delta_dia": round(a_dia - b_dia, 1),
        }

    # ---- Maiores leituras ---------------------------------------------------
    resultado["picos"] = sorted(medicoes, key=lambda m: (m.sistolica, m.diastolica), reverse=True)[:5]

    # ---- Séries para gráficos ----------------------------------------------
    resultado["series"] = {
        "labels": [f"{m.data:%d/%m/%y} {m.hora:%H:%M}" for m in medicoes],
        "sistolica": sis,
        "diastolica": dia,
        "pulsacao": [m.pulsacao for m in medicoes],
        "mm_sistolica": _media_movel(sis),
        "mm_diastolica": _media_movel(dia),
        "dispersao": [
            {"x": m.diastolica, "y": m.sistolica, "c": m.classificacao["hex"]} for m in medicoes
        ],
    }

    # Médias diárias (útil quando há várias medições por dia)
    diario = defaultdict(list)
    for m in medicoes:
        diario[m.data].append(m)
    dias_ordenados = sorted(diario)
    resultado["series_diarias"] = {
        "labels": [d.strftime("%d/%m/%y") for d in dias_ordenados],
        "sistolica": [_media(m.sistolica for m in diario[d]) for d in dias_ordenados],
        "diastolica": [_media(m.diastolica for m in diario[d]) for d in dias_ordenados],
    }
    return resultado


def intervalo_padrao(dias: int) -> tuple[date, date]:
    hoje = date.today()
    return hoje - timedelta(days=dias - 1), hoje

