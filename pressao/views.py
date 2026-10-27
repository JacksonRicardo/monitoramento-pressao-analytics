from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, UpdateView

from .analytics import analisar
from .exportacao_excel import gerar_excel
from .exportacao_pdf import gerar_pdf
from .forms import (
    SUGESTOES_OBSERVACOES,
    CadastroForm,
    ExportacaoForm,
    FiltroForm,
    ImportacaoForm,
    MedicaoForm,
    PerfilForm,
)
from .importacao import importar_planilha
from .models import FAIXAS_REFERENCIA, Medicao, Perfil

ATALHOS = [("7", "7 dias"), ("30", "30 dias"), ("90", "90 dias"), ("365", "1 ano"), ("todos", "Tudo")]


def _perfil(usuario):
    perfil, _ = Perfil.objects.get_or_create(usuario=usuario)
    return perfil


def _filtro_com_atalho(request):
    """Aplica atalhos de intervalo (?dias=30) convertendo em datas para o FiltroForm."""
    dados = request.GET.copy()
    dias = dados.get("dias")
    if dias and dias != "todos" and not (dados.get("inicio") or dados.get("fim")):
        try:
            hoje = timezone.localdate()
            dados["inicio"] = (hoje - timedelta(days=int(dias) - 1)).isoformat()
            dados["fim"] = hoje.isoformat()
        except ValueError:
            pass
    return FiltroForm(dados), dias


@login_required
def dashboard(request):
    base = Medicao.objects.filter(usuario=request.user)
    if not request.GET and base.exists():
        # Padrão: últimos 30 dias, se houver medições nesse intervalo
        limite = timezone.localdate() - timedelta(days=29)
        if base.filter(data__gte=limite).exists():
            return redirect(f"{request.path}?dias=30")
    filtro, dias = _filtro_com_atalho(request)
    medicoes = filtro.filtrar(base)
    perfil = _perfil(request.user)
    analise = analisar(medicoes, perfil)

    query_export = request.GET.copy()
    query_export.pop("dias", None)
    if filtro.is_valid():
        for chave in ("inicio", "fim"):
            if filtro.cleaned_data.get(chave):
                query_export[chave] = filtro.cleaned_data[chave].isoformat()

    contexto = {
        "filtro": filtro,
        "analise": analise,
        "perfil": perfil,
        "atalhos": ATALHOS,
        "dias": dias or ("" if request.GET else "todos"),
        "faixas": FAIXAS_REFERENCIA,
        "query_export": query_export.urlencode(),
        "total_geral": base.count(),
        "ultimas": base.order_by("-data", "-hora")[:5],
    }
    return render(request, "pressao/dashboard.html", contexto)


@login_required
def medicao_lista(request):
    filtro, dias = _filtro_com_atalho(request)
    medicoes = filtro.filtrar(Medicao.objects.filter(usuario=request.user)).order_by("-data", "-hora")
    resumo = medicoes.aggregate(
        media_sis=Avg("sistolica"),
        media_dia=Avg("diastolica"),
        media_pul=Avg("pulsacao"),
        max_sis=Max("sistolica"),
        max_dia=Max("diastolica"),
        min_sis=Min("sistolica"),
        min_dia=Min("diastolica"),
        total=Count("id"),
    )
    pagina = Paginator(medicoes, 15).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return render(
        request,
        "pressao/medicao_lista.html",
        {
            "pagina": pagina,
            "filtro": filtro,
            "resumo": resumo,
            "atalhos": ATALHOS,
            "dias": dias,
            "query": query.urlencode(),
        },
    )


class MedicaoMixin(LoginRequiredMixin):
    model = Medicao
    form_class = MedicaoForm
    template_name = "pressao/medicao_form.html"
    success_url = reverse_lazy("pressao:lista")

    def get_queryset(self):
        return Medicao.objects.filter(usuario=self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sugestoes"] = SUGESTOES_OBSERVACOES
        return ctx


class MedicaoCreateView(MedicaoMixin, CreateView):
    def get_initial(self):
        agora = timezone.localtime()
        return {"data": agora.date(), "hora": agora.strftime("%H:%M")}

    def form_valid(self, form):
        form.instance.usuario = self.request.user
        resposta = super().form_valid(form)
        m = self.object
        messages.success(
            self.request,
            f"Medição {m.sistolica}/{m.diastolica} registrada em {m.data:%d/%m/%Y} às {m.hora:%H:%M}.",
        )
        if "salvar_e_nova" in self.request.POST:
            return redirect("pressao:nova")
        return resposta


class MedicaoUpdateView(MedicaoMixin, UpdateView):
    def form_valid(self, form):
        messages.success(self.request, "Medição atualizada com sucesso.")
        return super().form_valid(form)


class MedicaoDeleteView(LoginRequiredMixin, DeleteView):
    model = Medicao
    template_name = "pressao/medicao_confirmar_exclusao.html"
    success_url = reverse_lazy("pressao:lista")

    def get_queryset(self):
        return Medicao.objects.filter(usuario=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Medição excluída.")
        return super().form_valid(form)


@login_required
def exportar(request):
    """Página de personalização da planilha / PDF."""
    form = ExportacaoForm.a_partir_da_query(request.GET)
    medicoes = form.filtrar(Medicao.objects.filter(usuario=request.user))
    return render(
        request,
        "pressao/exportar.html",
        {"form": form, "total": medicoes.count(), "query": request.GET.urlencode()},
    )


def _preparar_exportacao(request):
    form = ExportacaoForm.a_partir_da_query(request.GET)
    opcoes = form.opcoes()
    medicoes = form.filtrar(Medicao.objects.filter(usuario=request.user))
    medicoes = medicoes.order_by("data", "hora") if opcoes["ordem"] == "asc" else medicoes.order_by("-data", "-hora")
    medicoes = list(medicoes)
    analise = analisar(medicoes, _perfil(request.user))
    nome = f"controle_pressao_{timezone.localdate():%Y%m%d}"
    return medicoes, analise, opcoes, nome


@login_required
def exportar_excel(request):
    medicoes, analise, opcoes, nome = _preparar_exportacao(request)
    conteudo = gerar_excel(medicoes, analise, opcoes, request.user)
    resposta = HttpResponse(
        conteudo, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resposta["Content-Disposition"] = f'attachment; filename="{nome}.xlsx"'
    return resposta


@login_required
def exportar_pdf(request):
    medicoes, analise, opcoes, nome = _preparar_exportacao(request)
    conteudo = gerar_pdf(medicoes, analise, opcoes, request.user)
    resposta = HttpResponse(conteudo, content_type="application/pdf")
    disposicao = "inline" if request.GET.get("visualizar") else "attachment"
    resposta["Content-Disposition"] = f'{disposicao}; filename="{nome}.pdf"'
    return resposta


@login_required
def importar(request):
    form = ImportacaoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        resultado = importar_planilha(
            form.cleaned_data["arquivo"], request.user, form.cleaned_data["ignorar_duplicadas"]
        )
        if resultado.criadas:
            messages.success(request, f"{resultado.criadas} medição(ões) importada(s) com sucesso.")
        if resultado.ignoradas:
            messages.info(request, f"{resultado.ignoradas} medição(ões) já existente(s) foram ignoradas.")
        for erro in resultado.erros[:10]:
            messages.warning(request, erro)
        if len(resultado.erros) > 10:
            messages.warning(request, f"... e mais {len(resultado.erros) - 10} erro(s).")
        if not (resultado.criadas or resultado.ignoradas or resultado.erros):
            messages.info(request, "Nenhuma medição encontrada na planilha.")
        if resultado.criadas:
            return redirect("pressao:lista")
    return render(request, "pressao/importar.html", {"form": form})


@login_required
def modelo_planilha(request):
    """Baixa uma planilha em branco no formato do modelo original."""
    opcoes = ExportacaoForm.a_partir_da_query({}).opcoes()
    opcoes.update({"grafico": False, "analise": False, "instrucoes": True, "titulo": "Controle de Pressão Arterial"})
    conteudo = gerar_excel([], {"vazio": True}, opcoes, request.user)
    resposta = HttpResponse(
        conteudo, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resposta["Content-Disposition"] = 'attachment; filename="modelo_controle_pressao.xlsx"'
    return resposta


@login_required
def perfil(request):
    instancia = _perfil(request.user)
    form = PerfilForm(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Perfil atualizado.")
        return redirect("pressao:perfil")
    return render(request, "pressao/perfil.html", {"form": form})


def cadastro(request):
    if request.user.is_authenticated:
        return redirect("pressao:dashboard")
    form = CadastroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        login(request, usuario)
        messages.success(request, "Conta criada! Registre sua primeira medição.")
        return redirect("pressao:dashboard")
    return render(request, "registration/cadastro.html", {"form": form})
