from django.urls import include,path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import AdminLoginView,AdminPackViewSet,CatalogView,DashboardView,PaymentsView,StudentsView
app_name="admin_panel";router=DefaultRouter();router.register("packs",AdminPackViewSet,basename="admin-pack")
urlpatterns=[path("login/",AdminLoginView.as_view()),path("token/refresh/",TokenRefreshView.as_view()),path("dashboard/",DashboardView.as_view()),path("payments/",PaymentsView.as_view()),path("students/",StudentsView.as_view()),path("catalog/",CatalogView.as_view()),path("",include(router.urls))]
