from django.db import models
from django.conf import settings

class FeeCategory(models.Model):
    """Types of institutional fees (e.g. Tuition, Transport, Lab Fee)."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Fee Categories"

    def __str__(self):
        return self.name

class FeeStructure(models.Model):
    """Defines how much each class pays for a specific fee category."""
    class_name = models.ForeignKey('core.Class', on_delete=models.CASCADE, related_name='fee_structures')
    category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ('class_name', 'category')

    def __str__(self):
        return f"{self.category.name} - {self.class_name.name}: {self.amount}"

class Invoice(models.Model):
    """Primary billing document for a student per term."""
    STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='invoices')
    term = models.ForeignKey('core.AcademicTerm', on_delete=models.CASCADE)
    invoice_number = models.CharField(max_length=50, unique=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"INV-{self.invoice_number} ({self.student})"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            # Sequential-Safe Hash (More robust than hex[:10])
            import uuid
            import hashlib
            self.invoice_number = hashlib.md5(str(uuid.uuid4()).encode()).hexdigest()[:12].upper()
        super().save(*args, **kwargs)

class InvoiceItem(models.Model):
    """Line items for an invoice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.category.name} for {self.invoice.invoice_number}"

class Payment(models.Model):
    """Records of financial transactions against invoices."""
    METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('online', 'Online Payment'),
        ('cheque', 'Cheque'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    date_paid = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=20, choices=METHODS)
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Payment of {self.amount_paid} for {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        from django.db import transaction
        from django.db.models import F

        is_new = self.pk is None
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new:
                # 🛡️ BANK-GRADE ATOMICITY: Use F() expression to prevent race conditions
                # This ensures balance_due is updated directly on the database server.
                Invoice.objects.filter(id=self.invoice_id).update(
                    balance_due=F('balance_due') - self.amount_paid
                )
                
                # Refresh from DB to get the new atomic balance and update status
                self.invoice.refresh_from_db()
                if self.invoice.balance_due <= 0:
                    self.invoice.balance_due = 0
                    self.invoice.status = 'paid'
                elif self.invoice.balance_due < self.invoice.total_amount:
                    self.invoice.status = 'partial'
                
                # Optimization: Only save specific fields to avoid overwriting concurrent changes
                self.invoice.save(update_fields=['balance_due', 'status', 'updated_at'])
