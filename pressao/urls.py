from django.urls import path

from . import views

app_name = "pressao"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("medicoes/", views.medicao_lista, name="lista"),
    path("medicoes/nova/", views.MedicaoCreateView.as_view(), name="nova"),
    path("medicoes/<int:pk>/editar/", views.MedicaoUpdateView.as_view(), name="editar"),
    path("medicoes/<int:pk>/excluir/", views.MedicaoDeleteView.as_view(), name="excluir"),
    path("exportar/", views.exportar, name="exportar"),
    path("exportar/excel/", views.exportar_excel, name="exportar_excel"),
    path("exportar/pdf/", views.exportar_pdf, name="exportar_pdf"),
    path("importar/", views.importar, name="importar"),
    path("importar/modelo/", views.modelo_planilha, name="modelo"),
    path("perfil/", views.perfil, name="perfil"),
]

