from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PackViewSet

from .checkout_views import (
    CreateCheckoutView,
    MyPurchasesView,
    PurchaseDetailView,
    RefreshPurchaseView,
    chargily_webhook,
)

from .access_views import (
    ChapterAccessCheckView,
)


app_name = "payments"


router = DefaultRouter()

router.register(
    "packs",
    PackViewSet,
    basename="payment-pack",
)


urlpatterns = [
    # DRF router:
    # /api/payments/packs/
    # /api/payments/packs/<id>/
    path(
        "",
        include(router.urls),
    ),

    # -------------------------------------------------------
    # ACCESS CHECK
    # -------------------------------------------------------
    # IMPORTANT:
    # React PaidChapterRoute calls exactly this endpoint.
    #
    # GET /api/payments/access/chapters/14/
    path(
        "access/chapters/<int:chapter_id>/",
        ChapterAccessCheckView.as_view(),
        name="chapter-access-check",
    ),

    # -------------------------------------------------------
    # CHECKOUT
    # -------------------------------------------------------
    path(
        "checkout/",
        CreateCheckoutView.as_view(),
        name="create-checkout",
    ),

    path(
        "my-purchases/",
        MyPurchasesView.as_view(),
        name="my-purchases",
    ),

    path(
        "purchases/<uuid:purchase_id>/",
        PurchaseDetailView.as_view(),
        name="purchase-detail",
    ),

    path(
        "purchases/<uuid:purchase_id>/refresh/",
        RefreshPurchaseView.as_view(),
        name="refresh-purchase",
    ),

    path(
        "webhook/chargily/",
        chargily_webhook,
        name="chargily-webhook",
    ),
]
