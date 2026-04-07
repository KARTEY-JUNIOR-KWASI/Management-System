from django.contrib import admin
from .models import FeeCategory, FeeStructure, Invoice, InvoiceItem, Payment

@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('category', 'class_name', 'amount')
    list_filter = ('class_name', 'category')

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'student', 'term', 'total_amount', 'balance_due', 'status')
    list_filter = ('status', 'term')
    search_fields = ('invoice_number', 'student__user__first_name', 'student__user__last_name')
    inlines = [InvoiceItemInline]
    readonly_fields = ('invoice_number',)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount_paid', 'method', 'date_paid', 'transaction_id')
    list_filter = ('method', 'date_paid')
    search_fields = ('invoice__invoice_number', 'transaction_id')
