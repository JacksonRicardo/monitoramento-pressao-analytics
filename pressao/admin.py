from django.contrib import admin
from django.db.models import Avg
from django.http import HttpResponse
from django.utils.html import format_html

from .analytics import analisar
from .exportacao_excel import gerar_excel
from .forms import ExportacaoForm
from .models import Medicao, Perfil


class FaixaFilter(admin.SimpleListFilter):
    title = "faixa de referência"
    parameter_name = "faixa"

    def lookups(self, request, model_admin):
        return [
            ("elevada", "≥ 140/90"),
            ("muito_alta", "≥ 180/110"),
            ("normal", "< 140/90"),
        ]

    def queryset(self, request, queryset):
        from django.db.models import Q

        if self.value() == "elevada":
            return queryset.filter(Q(sistolica__gte=140) | Q(diastolica__gte=90))
        if self.value() == "muito_alta":
            return queryset.filter(Q(sistolica__gte=180) | Q(diastolica__gte=110))
        if self.value() == "normal":
            return queryset.filter(sistolica__lt=140, diastolica__lt=90)
        return queryset


@admin.register(Medicao)
class MedicaoAdmin(admin.ModelAdmin):
    list_display = ("data", "hora", "usuario", "pressao", "pulsacao", "periodo", "faixa", "observacoes")
    list_display_links = ("data", "hora")
    list_filter = ("periodo", FaixaFilter, "data", "usuario")
    search_fields = ("usuario__username", "usuario__first_name", "observacoes", "nota_profissional")
    date_hierarchy = "data"
    list_per_page = 25
    autocomplete_fields = ("usuario",)
    readonly_fields = ("criado_em", "atualizado_em", "faixa", "pam")
    actions = ["exportar_excel"]
    fieldsets = (
        ("Medição", {"fields": ("usuario", ("data", "hora"), ("sistolica", "diastolica", "pulsacao"), "periodo")}),
        ("Anotações", {"fields": ("observacoes", "nota_profissional")}),
        ("Calculado", {"fields": ("faixa", "pam", "criado_em", "atualizado_em")}),
    )

    @admin.display(description="Pressão", ordering="sistolica")
    def pressao(self, obj):
        return f"{obj.sistolica}/{obj.diastolica}"

    @admin.display(description="Faixa")
    def faixa(self, obj):
        c = obj.classificacao
        return format_html(
            '<span class="badge" style="background:{};color:#fff">{}</span>', c["hex"], c["rotulo"]
        )

    @admin.display(description="PAM")
    def pam(self, obj):
        return f"{obj.pressao_media_arterial} mmHg"

    @admin.action(description="Exportar selecionadas para Excel")
    def exportar_excel(self, request, queryset):
        medicoes = list(queryset.order_by("data", "hora"))
        opcoes = ExportacaoForm.a_partir_da_query({}).opcoes()
        opcoes["colunas"].append("classificacao")
        conteudo = gerar_excel(medicoes, analisar(medicoes), opcoes, request.user)
        resposta = HttpResponse(
            conteudo, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        resposta["Content-Disposition"] = 'attachment; filename="medicoes_admin.xlsx"'
        return resposta

    def changelist_view(self, request, extra_context=None):
        resposta = super().changelist_view(request, extra_context)
        try:
            qs = resposta.context_data["cl"].queryset
            medias = qs.aggregate(s=Avg("sistolica"), d=Avg("diastolica"), p=Avg("pulsacao"))
            if medias["s"]:
                resposta.context_data["title"] = (
                    f"Medições — média {medias['s']:.0f}/{medias['d']:.0f} mmHg"
                    + (f" · pulso {medias['p']:.0f} bpm" if medias["p"] else "")
                )
        except (AttributeError, KeyError):
            pass
        return resposta


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "nome", "idade", "medico_responsavel", "meta", "total_medicoes")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "medico_responsavel")
    autocomplete_fields = ("usuario",)

    @admin.display(description="Nome")
    def nome(self, obj):
        return obj.usuario.get_full_name() or "-"

    @admin.display(description="Meta")
    def meta(self, obj):
        return f"{obj.meta_sistolica}/{obj.meta_diastolica}" if obj.tem_meta else "-"

    @admin.display(description="Medições")
    def total_medicoes(self, obj):
        return obj.usuario.medicoes.count()

