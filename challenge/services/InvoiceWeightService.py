from challenge.models import InvoiceItem
from django.db.models import Case, When, F, Value, FloatField

class InvoiceWeightService:
    def __init__(self, invoices):
        self.invoices = invoices

    def calculate_total_weight(self):
        weight_annotation = Case(
            When(unidade_comercial="SC", 
                 then=F("quantidade_comercial") * 60),
            When(unidade_comercial="KG", 
                 then=F("quantidade_comercial")),
            default=Value(0, output_field=FloatField()),
            output_field=FloatField(),
        )

        invoice_items = InvoiceItem.objects.filter(invoice__in=self.invoices).annotate(peso_kg=weight_annotation)

        return invoice_items
