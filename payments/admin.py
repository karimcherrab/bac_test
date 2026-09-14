from django.contrib import admin

from .models import (
    ChargilyCustomerLink,
    Pack,
    Purchase,
    StudentAccess,
)


@admin.register(Pack)
class PackAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "pack_type",
        "price_dzd",
        "chapter",
        "subject",
        "is_active",
        "updated_at",
    ]
    list_filter = [
        "pack_type",
        "is_active",
    ]
    search_fields = [
        "name",
        "chapter__title",
        "subject__name",
    ]


@admin.register(
    ChargilyCustomerLink
)
class ChargilyCustomerLinkAdmin(
    admin.ModelAdmin
):
    list_display = [
        "student",
        "environment",
        "customer_id",
        "email_snapshot",
        "updated_at",
    ]
    list_filter = [
        "environment",
    ]
    search_fields = [
        "student__username",
        "student__email",
        "customer_id",
        "email_snapshot",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(Purchase)
class PurchaseAdmin(
    admin.ModelAdmin
):
    list_display = [
        "id",
        "student",
        "customer_email",
        "pack",
        "amount_dzd",
        "status",
        "payment_method",
        "paid_at",
        "created_at",
    ]
    list_filter = [
        "status",
        "payment_method",
    ]
    search_fields = [
        "chargily_checkout_id",
        "chargily_customer_id",
        "customer_email",
        "student__email",
    ]
    readonly_fields = [
        "provider_data",
        "webhook_data",
        "created_at",
        "updated_at",
    ]


@admin.register(StudentAccess)
class StudentAccessAdmin(
    admin.ModelAdmin
):
    list_display = [
        "student",
        "subject",
        "chapter",
        "source_purchase",
        "created_at",
    ]
    search_fields = [
        "student__username",
        "student__email",
        "subject__name",
        "chapter__title",
    ]
