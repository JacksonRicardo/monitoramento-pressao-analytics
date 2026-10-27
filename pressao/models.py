"""Modelos do controle de pressão arterial.

Os campos espelham as colunas da planilha original:
Data | Hora | Sistólica | Diastólica | Pulsação | Período | Nota do profissional | Observações
"""
from datetime import date, time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Periodo(models.TextChoices):
    MANHA = "Manhã", "Manhã"
    TARDE = "Tarde", "Tarde"
    NOITE = "Noite", "Noite"


def periodo_por_hora(hora: time | None) -> str:
    """Sugere o período do dia a partir do horário da medição."""
    if hora is None:
        return Periodo.MANHA
    if 5 <= hora.hour < 12:
        return Periodo.MANHA
    if 12 <= hora.hour < 18:
        return Periodo.TARDE
    return Periodo.NOITE


# Faixas de referência (Diretrizes Brasileiras de Hipertensão Arterial – 2020).
# Usadas apenas para fins informativos/estatísticos; NÃO constituem diagnóstico.
FAIXAS_REFERENCIA = [
    # (chave, rótulo, sist_min, diast_min, cor bootstrap, cor hex)
    ("otima", "Ótima", 0, 0, "success", "#198754"),
    ("normal", "Normal", 120, 80, "info", "#0dcaf0"),
    ("pre", "Pré-hipertensão", 130, 85, "warning", "#ffc107"),
    ("ha1", "Estágio 1", 140, 90, "orange", "#fd7e14"),
    ("ha2", "Estágio 2", 160, 100, "danger", "#dc3545"),
    ("ha3", "Estágio 3", 180, 110, "dark", "#842029"),
]


def classificar(sistolica: int, diastolica: int) -> dict:
    """Retorna a faixa de referência mais alta atingida por qualquer um dos valores."""
    escolhida = FAIXAS_REFERENCIA[0]
    for faixa in FAIXAS_REFERENCIA:
        _, _, s_min, d_min, _, _ = faixa
        if sistolica >= s_min or diastolica >= d_min:
            escolhida = faixa
    chave, rotulo, _, _, cor, hexa = escolhida
    return {"chave": chave, "rotulo": rotulo, "cor": cor, "hex": hexa}


class Perfil(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil", verbose_name="usuário"
    )
    data_nascimento = models.DateField("data de nascimento", null=True, blank=True)
    medico_responsavel = models.CharField("profissional responsável", max_length=120, blank=True)
    medicamentos = models.TextField("medicamentos em uso", blank=True)
    meta_sistolica = models.PositiveSmallIntegerField(
        "meta sistólica",
        null=True,
        blank=True,
        validators=[MinValueValidator(70), MaxValueValidator(250)],
        help_text="Defina apenas se orientado pelo seu profissional de saúde.",
    )
    meta_diastolica = models.PositiveSmallIntegerField(
        "meta diastólica",
        null=True,
        blank=True,
        validators=[MinValueValidator(40), MaxValueValidator(150)],
        help_text="Defina apenas se orientado pelo seu profissional de saúde.",
    )

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfis"

    def __str__(self):
        return f"Perfil de {self.usuario.get_full_name() or self.usuario.username}"

    @property
    def idade(self):
        if not self.data_nascimento:
            return None
        hoje = date.today()
        nasc = self.data_nascimento
        return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))

    @property
    def tem_meta(self):
        return bool(self.meta_sistolica and self.meta_diastolica)


class Medicao(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="medicoes", verbose_name="usuário"
    )
    data = models.DateField("data", default=date.today)
    hora = models.TimeField("hora")
    sistolica = models.PositiveSmallIntegerField(
        "sistólica (máxima)", validators=[MinValueValidator(50), MaxValueValidator(300)]
    )
    diastolica = models.PositiveSmallIntegerField(
        "diastólica (mínima)", validators=[MinValueValidator(30), MaxValueValidator(200)]
    )
    pulsacao = models.PositiveSmallIntegerField(
        "pulsação (bpm)", null=True, blank=True, validators=[MinValueValidator(25), MaxValueValidator(250)]
    )
    periodo = models.CharField("período", max_length=10, choices=Periodo.choices, blank=True)
    nota_profissional = models.CharField("nota do profissional", max_length=255, blank=True)
    observacoes = models.CharField("observações", max_length=255, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "medição"
        verbose_name_plural = "medições"
        ordering = ["-data", "-hora"]
        indexes = [models.Index(fields=["usuario", "data"])]

    def __str__(self):
        return f"{self.data:%d/%m/%Y} {self.hora:%H:%M} – {self.sistolica}/{self.diastolica}"

    def clean(self):
        if self.sistolica and self.diastolica and self.diastolica >= self.sistolica:
            raise ValidationError({"diastolica": "A diastólica deve ser menor que a sistólica."})

    def save(self, *args, **kwargs):
        if not self.periodo:
            self.periodo = periodo_por_hora(self.hora)
        super().save(*args, **kwargs)

    @property
    def classificacao(self) -> dict:
        return classificar(self.sistolica, self.diastolica)

    @property
    def pressao_media_arterial(self) -> int:
        """PAM = (PAS + 2·PAD) / 3."""
        return round((self.sistolica + 2 * self.diastolica) / 3)

    @property
    def pressao_pulso(self) -> int:
        return self.sistolica - self.diastolica

