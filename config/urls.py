from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from pressao import views as pressao_views

admin.site.site_header = "Controle de Pressão"
admin.site.site_title = "Pressão Admin"
admin.site.index_title = "Administração"

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "entrar/",
        auth_views.LoginView.as_view(template_name="registration/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("cadastro/", pressao_views.cadastro, name="cadastro"),
    path("", include("pressao.urls")),
]

