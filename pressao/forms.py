from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Medicao, Perfil, Periodo

SUGESTOES_OBSERVACOES = [
    "Em repouso",
    "Ao acordar",
    "Antes de dormir",
    "Após refeição",
    "Após medicação",
    "Em jejum",
    "Após exercício",
    "Com dor de cabeça",
    "Estressado(a)",
]


class BootstrapMixin:
    """Aplica classes do Bootstrap 5 automaticamente nos widgets."""

    def _aplicar_bootstrap(self):
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")

    def full_clean(self):
        super().full_clean()
        # Marca os campos com erro para exibir o estilo de validação do Bootstrap
        for nome in self.errors:
            if nome in self.fields:
                attrs = self.fields[nome].widget.attrs
                if "is-invalid" not in attrs.get("class", ""):
                    attrs["class"] = (attrs.get("class", "") + " is-invalid").strip()


class MedicaoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Medicao
        fields = [
            "data",
            "hora",
            "sistolica",
            "diastolica",
            "pulsacao",
            "periodo",
            "observacoes",
            "nota_profissional",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "sistolica": forms.NumberInput(attrs={"placeholder": "ex: 120", "inputmode": "numeric"}),
            "diastolica": forms.NumberInput(attrs={"placeholder": "ex: 80", "inputmode": "numeric"}),
            "pulsacao": forms.NumberInput(attrs={"placeholder": "ex: 72", "inputmode": "numeric"}),
            "observacoes": forms.TextInput(attrs={"list": "sugestoes-observacoes", "placeholder": "ex: Em repouso"}),
            "nota_profissional": forms.TextInput(attrs={"placeholder": "Opcional, com orientação profissional"}),
        }
        help_texts = {"periodo": "Se deixado em branco, é definido automaticamente pela hora."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["periodo"].choices = [("", "Automático (pela hora)")] + list(Periodo.choices)
        self._aplicar_bootstrap()


class PerfilForm(BootstrapMixin, forms.ModelForm):
    first_name = forms.CharField(label="Nome", max_length=150, required=False)
    last_name = forms.CharField(label="Sobrenome", max_length=150, required=False)
    email = forms.EmailField(label="E-mail", required=False)

    class Meta:
        model = Perfil
        fields = ["data_nascimento", "medico_responsavel", "medicamentos", "meta_sistolica", "meta_diastolica"]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "medicamentos": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuario = self.instance.usuario
        self.fields["first_name"].initial = usuario.first_name
        self.fields["last_name"].initial = usuario.last_name
        self.fields["email"].initial = usuario.email
        # Reordena para os dados pessoais aparecerem primeiro
        self.order_fields(["first_name", "last_name", "email"] + self.Meta.fields)
        self._aplicar_bootstrap()

    def clean(self):
        dados = super().clean()
        s, d = dados.get("meta_sistolica"), dados.get("meta_diastolica")
        if bool(s) != bool(d):
            raise forms.ValidationError("Informe as duas metas (sistólica e diastólica) ou nenhuma.")
        if s and d and d >= s:
            raise forms.ValidationError("A meta diastólica deve ser menor que a sistólica.")
        return dados

    def save(self, commit=True):
        perfil = super().save(commit=False)
        usuario = perfil.usuario
        usuario.first_name = self.cleaned_data["first_name"]
        usuario.last_name = self.cleaned_data["last_name"]
        usuario.email = self.cleaned_data["email"]
        if commit:
            usuario.save()
            perfil.save()
        return perfil


class CadastroForm(BootstrapMixin, UserCreationForm):
    first_name = forms.CharField(label="Nome", max_length=150)
    email = forms.EmailField(label="E-mail", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()


class FiltroForm(BootstrapMixin, forms.Form):
    """Filtro usado na listagem, no dashboard e nas exportações."""

    inicio = forms.DateField(label="De", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    fim = forms.DateField(label="Até", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    periodo = forms.ChoiceField(
        label="Período", required=False, choices=[("", "Todos")] + list(Periodo.choices)
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aplicar_bootstrap()

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("inicio"), dados.get("fim")
        if inicio and fim and inicio > fim:
            raise forms.ValidationError("A data inicial deve ser anterior à data final.")
        return dados

    def filtrar(self, queryset):
        if not self.is_valid():
            return queryset
        dados = self.cleaned_data
        if dados.get("inicio"):
            queryset = queryset.filter(data__gte=dados["inicio"])
        if dados.get("fim"):
            queryset = queryset.filter(data__lte=dados["fim"])
        if dados.get("periodo"):
            queryset = queryset.filter(periodo=dados["periodo"])
        return queryset


COLUNAS_EXPORTACAO = [
    ("pulsacao", "Pulsação"),
    ("periodo", "Período"),
    ("nota_profissional", "Nota do profissional"),
    ("observacoes", "Observações"),
    ("classificacao", "Faixa de referência"),
    ("pam", "Pressão arterial média (PAM)"),
]

CORES_TEMA = [
    ("C0392B", "Vermelho"),
    ("1F4E79", "Azul"),
    ("1E8449", "Verde"),
    ("6C3483", "Roxo"),
    ("2C3E50", "Grafite"),
]


class ExportacaoForm(FiltroForm):
    titulo = forms.CharField(
        label="Título do relatório", max_length=80, required=False, initial="Controle de Pressão Arterial"
    )
    colunas = forms.MultipleChoiceField(
        label="Colunas adicionais",
        required=False,
        choices=COLUNAS_EXPORTACAO,
        initial=["pulsacao", "periodo", "nota_profissional", "observacoes"],
        widget=forms.CheckboxSelectMultiple,
    )
    incluir_estatisticas = forms.BooleanField(label="Incluir estatísticas", required=False, initial=True)
    incluir_grafico = forms.BooleanField(label="Incluir gráfico de evolução", required=False, initial=True)
    incluir_analise = forms.BooleanField(
        label="Incluir análise por período e faixas", required=False, initial=True
    )
    incluir_instrucoes = forms.BooleanField(label="Incluir aba/página de instruções", required=False, initial=False)
    destacar_elevadas = forms.BooleanField(
        label="Destacar leituras ≥ 140/90", required=False, initial=True
    )
    cor = forms.ChoiceField(label="Cor do tema", choices=CORES_TEMA, initial="C0392B")
    ordem = forms.ChoiceField(
        label="Ordenação",
        choices=[("asc", "Mais antigas primeiro"), ("desc", "Mais recentes primeiro")],
        initial="asc",
    )

    @classmethod
    def a_partir_da_query(cls, query):
        """Cria o formulário a partir da querystring.

        Links rápidos (ex.: botão "Baixar Excel" do dashboard) enviam apenas os filtros;
        nesse caso as opções de personalização assumem os valores padrão.
        """
        if "titulo" in query:
            return cls(query)
        dados = {}
        for nome, campo in cls.base_fields.items():
            if campo.initial in (None, False):
                continue
            dados[nome] = campo.initial
        for chave in ("inicio", "fim", "periodo"):
            if query.get(chave):
                dados[chave] = query.get(chave)
        return cls(dados)

    def opcoes(self) -> dict:
        """Opções normalizadas (com valores padrão quando o formulário não é válido)."""
        if self.is_valid():
            d = self.cleaned_data
        else:
            d = {nome: campo.initial for nome, campo in self.fields.items()}
        return {
            "titulo": d.get("titulo") or "Controle de Pressão Arterial",
            "colunas": list(d.get("colunas") or []),
            "estatisticas": bool(d.get("incluir_estatisticas")),
            "grafico": bool(d.get("incluir_grafico")),
            "analise": bool(d.get("incluir_analise")),
            "instrucoes": bool(d.get("incluir_instrucoes")),
            "destacar": bool(d.get("destacar_elevadas")),
            "cor": d.get("cor") or "C0392B",
            "ordem": d.get("ordem") or "asc",
            "inicio": d.get("inicio"),
            "fim": d.get("fim"),
            "periodo": d.get("periodo") or "",
        }


class ImportacaoForm(forms.Form):
    arquivo = forms.FileField(
        label="Planilha (.xlsx)",
        help_text="Use o mesmo modelo da planilha de controle: Data, Hora, Sistólica, Diastólica, Pulsação, "
        "Período, Nota do profissional, Observações.",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".xlsx"}),
    )
    ignorar_duplicadas = forms.BooleanField(
        label="Ignorar medições já existentes (mesma data e hora)",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if not arquivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Envie um arquivo no formato .xlsx.")
        if arquivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("O arquivo deve ter no máximo 5 MB.")
        return arquivo
