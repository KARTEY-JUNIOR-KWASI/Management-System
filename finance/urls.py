from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('dashboard/', views.finance_hub, name='finance_hub'),
    path('billing/generate/', views.generate_class_invoices, name='generate_invoices'),
    path('payment/<int:invoice_id>/record/', views.record_payment, name='record_payment'),
    path('payment/<int:payment_id>/receipt/', views.generate_payment_receipt, name='generate_receipt'),
]
