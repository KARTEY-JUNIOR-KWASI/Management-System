from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('dashboard/', views.finance_hub, name='finance_hub'),
    path('billing/generate/', views.generate_class_invoices, name='generate_invoices'),
    path('payment/<int:invoice_id>/record/', views.record_payment, name='record_payment'),
    path('payment/<int:payment_id>/receipt/', views.generate_payment_receipt, name='generate_receipt'),
    
    # ⚙️ Institutional Fee Management
    path('category/add/', views.manage_fee_category, name='add_category'),
    path('category/<int:pk>/edit/', views.manage_fee_category, name='edit_category'),
    path('structure/add/', views.manage_fee_structure, name='add_structure'),
    path('structure/<int:pk>/edit/', views.manage_fee_structure, name='edit_structure'),
    path('student/', views.student_finance_hub, name='student_finance_hub'),
]
