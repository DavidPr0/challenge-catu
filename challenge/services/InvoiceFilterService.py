from django.db.models import Q
from challenge.models import Invoice

class InvoiceFilterService:
    def __init__(self, document_number=None, document_type=None, cfop=None, date_min=None, date_max=None, invoice_type=None):
        self.document_number = document_number
        self.document_type = document_type
        self.cfop = cfop
        self.date_min = date_min
        self.date_max = date_max
        self.invoice_type = invoice_type

    def filter_invoices(self):
        invoices = Invoice.objects.filter(is_deleted=False)

        if self.document_number and self.document_type:
            if self.document_type == "cpf":
                invoices = invoices.filter(
                    Q(cpf_emitente=self.document_number) | Q(cpf_destinatario=self.document_number)
                )
            elif self.document_type == "cnpj":
                invoices = invoices.filter(
                    Q(cnpj_emitente=self.document_number) | Q(cnpj_destinatario=self.document_number)
                )

        if self.cfop:
            invoices = invoices.filter(invoiceitem__cfop=self.cfop)

        if self.date_min:
            invoices = invoices.filter(data_emissao__gte=self.date_min)

        if self.date_max:
            invoices = invoices.filter(data_emissao__lte=self.date_max)

        if self.date_min and self.date_max:
            invoices = invoices.filter(data_emissao__range=(self.date_min, self.date_max))

        if self.invoice_type == "0":
            invoices = invoices.filter(cnpj_destinatario=self.document_number)
        elif self.invoice_type == "1":
            invoices = invoices.filter(
                cnpj_emitente=self.document_number, status="autorizado"
            )

        return invoices
