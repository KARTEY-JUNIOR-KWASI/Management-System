from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from decimal import Decimal
from .models import FeeCategory, FeeStructure, Invoice, InvoiceItem, Payment
from students.models import Student
from core.models import Class, AcademicTerm, SchoolConfiguration
from .services import FinanceService
from .forms import FeeCategoryForm, FeeStructureForm

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from analytics.reporting_utils import draw_institutional_seal
from accounts.decorators import admin_required, student_required

@admin_required
def finance_hub(request):
    """Institutional Financial Pulse Dashboard."""
    config = SchoolConfiguration.get_config()
    active_term = config.active_term
    
    # Financial Analytics
    if active_term:
        total_expected = Invoice.objects.filter(term=active_term).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        total_collected = Payment.objects.filter(invoice__term=active_term).aggregate(Sum('amount_paid'))['amount_paid__sum'] or Decimal('0.00')
        unpaid_invoices = Invoice.objects.filter(term=active_term, status__in=['unpaid', 'partial']).select_related('student__user')[:10]
    else:
        total_expected = Decimal('0.00')
        total_collected = Decimal('0.00')
        unpaid_invoices = Invoice.objects.none()

    outstanding_debt = total_expected - total_collected
    
    collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
    
    recent_payments = Payment.objects.select_related('invoice__student__user').order_by('-date_paid')[:10]
    
    classes = Class.objects.all().order_by('grade', 'name')
    categories = FeeCategory.objects.all().order_by('name')
    structures = FeeStructure.objects.select_related('class_name', 'category').order_by('class_name__grade', 'category__name')
    
    # Financial Velocity Pulse Aggregation (Last 6 Months)
    from django.db.models.functions import TruncMonth
    from datetime import datetime, timedelta
    
    # Calculate start date for 6 months ago
    six_months_ago = datetime.now().replace(day=1) - timedelta(days=150) # Approx 6 months
    
    # Aggregate Collections (Payments)
    monthly_collected_qs = Payment.objects.filter(
        date_paid__gte=six_months_ago
    ).annotate(
        month=TruncMonth('date_paid')
    ).values('month').annotate(
        total=Sum('amount_paid')
    ).order_by('month')
    
    # Aggregate Projections (Invoices)
    monthly_expected_qs = Invoice.objects.filter(
        created_at__gte=six_months_ago
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total=Sum('total_amount')
    ).order_by('month')
    
    # Prepare Data for Chart.js
    chart_labels = []
    chart_expected = []
    chart_collected = []
    
    # Create a map for easy lookup
    collected_map = {item['month'].strftime('%b %Y'): float(item['total']) for item in monthly_collected_qs}
    expected_map = {item['month'].strftime('%b %Y'): float(item['total']) for item in monthly_expected_qs}
    
    # Generate labels for last 6 months
    for i in range(5, -1, -1):
        d = datetime.now() - timedelta(days=i*30)
        label = d.strftime('%b %Y')
        chart_labels.append(label)
        chart_expected.append(expected_map.get(label, 0.0))
        chart_collected.append(collected_map.get(label, 0.0))

    context = {
        'total_expected': total_expected,
        'total_collected': total_collected,
        'outstanding_debt': outstanding_debt,
        'collection_rate': round(collection_rate, 1),
        'recent_payments': recent_payments,
        'unpaid_invoices': unpaid_invoices,
        'active_term': active_term,
        'classes': classes,
        'categories': categories,
        'structures': structures,
        'category_form': FeeCategoryForm(),
        'structure_form': FeeStructureForm(),
        # Chart Data
        'chart_labels': chart_labels,
        'chart_expected': chart_expected,
        'chart_collected': chart_collected,
    }
    return render(request, 'admin_dashboard/finance_hub.html', context)

@admin_required
def generate_class_invoices(request):
    """Institutional Bulk Billing Engine: O(1) performance refactor using service delegation."""
    if request.method == 'POST':
        class_id = request.POST.get('class_id')
        term_id = request.POST.get('term_id')
        
        target_class = get_object_or_404(Class, id=class_id)
        target_term = get_object_or_404(AcademicTerm, id=term_id)
        
        try:
            invoice_count = FinanceService.generate_class_billing(target_class, target_term)
            if invoice_count > 0:
                messages.success(request, f'Synchronized {invoice_count} primary invoices for {target_class.name}.')
            else:
                messages.info(request, f'No new invoices needed or fee structures missing for {target_class.name}.')
        except Exception as e:
            messages.error(request, f'Billing protocol interrupted: {str(e)}')
            
    return redirect('finance:finance_hub')

@admin_required
def record_payment(request, invoice_id):
    """Manual payment recording by administrator."""
    invoice = get_object_or_404(Invoice, id=invoice_id)
    if request.method == 'POST':
        try:
            amount = Decimal(request.POST.get('amount'))
            method = request.POST.get('method')
            ref = request.POST.get('reference', '')
            
            if amount <= 0:
                messages.error(request, 'Payment amount must be greater than zero.')
            elif amount > invoice.balance_due:
                messages.error(request, f'Payment exceeds balance. Max allowed: {invoice.balance_due}')
            else:
                FinanceService.record_payment(
                    invoice=invoice,
                    amount=amount,
                    method=method,
                    transaction_id=ref
                )
                messages.success(request, f'Recorded payment of {amount} for {invoice.student.user.get_full_name()}.')
        except Exception as e:
            messages.error(request, f'Transaction failed: {str(e)}')
            
    return redirect('finance:finance_hub')

@admin_required
def generate_payment_receipt(request, payment_id):
    """Generate a professional, print-ready PDF receipt for a transaction."""
    payment = get_object_or_404(Payment, id=payment_id)
    student = payment.invoice.student
    config = SchoolConfiguration.get_config()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Receipt_{payment.transaction_id or payment.id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A5, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    styles = getSampleStyleSheet()
    story = []

    # Custom Styles
    styles.add(ParagraphStyle(name='Title', parent=styles['Heading1'], alignment=1, fontSize=16, spaceAfter=20, textColor=colors.HexColor('#1E293B')))
    styles.add(ParagraphStyle(name='SubTitle', parent=styles['Normal'], alignment=1, fontSize=10, textColor=colors.grey))
    styles.add(ParagraphStyle(name='SectionHeader', parent=styles['Heading2'], fontSize=12, spaceBefore=15, spaceAfter=8, textColor=colors.HexColor('#4361EE')))

    # Header
    seal = draw_institutional_seal()
    h_data = [[seal, Paragraph(f"<b>{config.name}</b><br/>{config.motto}<br/>{config.address}", styles['SubTitle'])]]
    h_table = Table(h_data, colWidths=[2.5*cm, 9*cm])
    h_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (0,0), 'CENTER')]))
    story.append(h_table)
    story.append(Spacer(1, 15))

    # Title
    story.append(Paragraph("OFFICIAL PAYMENT RECEIPT", styles['Title']))
    story.append(Paragraph(f"<b>No:</b> {payment.transaction_id or payment.id} | <b>Date:</b> {payment.date_paid.strftime('%B %d, %Y')}", styles['SubTitle']))
    story.append(Spacer(1, 20))

    # Transaction Details
    story.append(Paragraph("PAYMENT DETAILS", styles['SectionHeader']))
    p_data = [
        ['STUDENT:', f"{student.user.get_full_name()} ({student.student_id})"],
        ['CLASS:', f"{student.class_enrolled.name} {student.class_enrolled.section}"],
        ['TERM:', payment.invoice.term.name],
        ['METHOD:', payment.get_method_display()],
    ]
    p_table = Table(p_data, colWidths=[3*cm, 8.5*cm])
    p_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
    ]))
    story.append(p_table)
    story.append(Spacer(1, 20))

    # Amount Table
    story.append(Paragraph("AMOUNT SUMMARY", styles['SectionHeader']))
    currency = config.currency_symbol or "GH₵"
    a_data = [
        ['DESCRIPTION', 'AMOUNT'],
        [f"Payment for Invoice {payment.invoice.invoice_number}", f"{currency}{payment.amount_paid}"],
        ['<b>TOTAL PAID</b>', f"<b>{currency}{payment.amount_paid}</b>"],
    ]
    a_table = Table(a_data, colWidths=[8.5*cm, 3*cm])
    a_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4361EE')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(a_table)

    # Footer
    story.append(Spacer(1, 40))
    f_data = [['__________________________', '__________________________'], ['Cashier Signature', 'Parent/Guardian Signature']]
    f_table = Table(f_data, colWidths=[5.75*cm, 5.75*cm])
    f_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTSIZE', (0, 1), (-1, -1), 8), ('TEXTCOLOR', (0, 1), (-1, -1), colors.grey)]))
    story.append(f_table)

    doc.build(story)
    return response

@admin_required
def manage_fee_category(request, pk=None):
    """CRUD view for individual fee category definitions."""
    category = get_object_or_404(FeeCategory, pk=pk) if pk else None
    
    if request.method == 'POST':
        form = FeeCategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Fee category {"updated" if category else "created"} successfully.')
        else:
            messages.error(request, 'Failed to save fee category. Please check your inputs.')
    elif request.method == 'DELETE' or (request.method == 'POST' and '_delete' in request.POST):
        if category:
            name = category.name
            category.delete()
            messages.warning(request, f'Fee category "{name}" has been decommissioned.')
            
    return redirect('finance:finance_hub')

@admin_required
def manage_fee_structure(request, pk=None):
    """CRUD view for class-specific fee structure amounts."""
    structure = get_object_or_404(FeeStructure, pk=pk) if pk else None
    
    if request.method == 'POST':
        # Handle deletion
        if '_delete' in request.POST and structure:
            structure.delete()
            messages.warning(request, 'Fee structure removed.')
            return redirect('finance:finance_hub')
            
        form = FeeStructureForm(request.POST, instance=structure)
        if form.is_valid():
            form.save()
            messages.success(request, f'Fee structure {"updated" if structure else "created"} successfully.')
        else:
            messages.error(request, 'Failed to save fee structure. Please check your inputs.')
            
    return redirect('finance:finance_hub')

@student_required
def student_finance_hub(request):
    """Student-facing personal financial dashboard."""
    student = get_object_or_404(Student, user=request.user)
    invoices = Invoice.objects.filter(student=student).order_by("-created_at")
    payments = Payment.objects.filter(invoice__student=student).order_by("-date_paid")
    
    total_invoiced = invoices.aggregate(Sum("total_amount"))["total_amount__sum"] or Decimal("0.00")
    total_paid = payments.aggregate(Sum("amount_paid"))["amount_paid__sum"] or Decimal("0.00")
    balance = total_invoiced - total_paid
    
    context = {
        "student": student,
        "invoices": invoices,
        "payments": payments,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "balance": balance,
    }
    return render(request, "students/finance_hub.html", context)


