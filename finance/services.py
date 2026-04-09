from django.db import transaction
from django.db.models import F
from .models import Invoice, InvoiceItem, Payment, FeeStructure
from students.models import Student

class FinanceService:
    @staticmethod
    @transaction.atomic
    def generate_class_billing(target_class, target_term):
        """
        Executes high-speed bulk billing for an entire class.
        Returns the number of student invoices generated.
        """
        # 1. Identify fee structures
        structures = list(FeeStructure.objects.filter(class_name=target_class))
        if not structures:
            return 0
            
        # 2. Filter students who are not yet billed for this term
        existing_student_ids = Invoice.objects.filter(
            term=target_term, 
            student__class_enrolled=target_class
        ).values_list('student_id', flat=True)
        
        eligible_students = Student.objects.filter(
            class_enrolled=target_class
        ).exclude(id__in=existing_student_ids)

        # 3. Process Billing
        invoice_count = 0
        base_total = sum(fee.amount for fee in structures)
        
        for student in eligible_students:
            invoice = Invoice.objects.create(
                student=student, 
                term=target_term,
                total_amount=base_total,
                balance_due=base_total
            )
            
            # Batch creation of line items
            items = [
                InvoiceItem(
                    invoice=invoice,
                    category=fee.category,
                    amount=fee.amount
                ) for fee in structures
            ]
            InvoiceItem.objects.bulk_create(items)
            invoice_count += 1
            
        return invoice_count

    @staticmethod
    @transaction.atomic
    def record_payment(invoice, amount, method, transaction_id=None, notes=''):
        """
        Records a transaction against an invoice with Bank-Grade atomicity.
        """
        # 1. Create the Payment record
        payment = Payment.objects.create(
            invoice=invoice,
            amount_paid=amount,
            method=method,
            transaction_id=transaction_id,
            notes=notes
        )
        
        # 2. Atomic Balance Adjustment
        # This occurs at the DB level, preventing race conditions.
        Invoice.objects.filter(id=invoice.id).update(
            balance_due=F('balance_due') - amount
        )
        
        # 3. Synchronize status
        invoice.refresh_from_db()
        if invoice.balance_due <= 0:
            invoice.balance_due = 0
            invoice.status = 'paid'
        elif invoice.balance_due < invoice.total_amount:
            invoice.status = 'partial'
        
        invoice.save(update_fields=['balance_due', 'status', 'updated_at'])
        
        return payment
