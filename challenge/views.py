from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q, Sum, F, Case, When, Value, FloatField, Prefetch
from django.db.models.functions import Coalesce

from .models import Invoice, InvoiceItem
from .serializers import InvoiceSerializer
from .services.InvoiceFilterService import InvoiceFilterService
from .services.InvoiceWeightService import InvoiceWeightService

from rest_framework import status
from datetime import datetime, timedelta

class ChallengeViewset(viewsets.ViewSet):
    @action(detail=False, methods=["get"], url_path="list/all")
    def list_all(self, request):
        document_number = request.query_params.get('document_number')
        document_type = request.query_params.get('document_type')
        cfop = request.query_params.get('cfop')
        date_min = request.query_params.get('date_min')
        date_max = request.query_params.get('date_max')
        invoice_type = request.query_params.get('type')

        filter_service = InvoiceFilterService(
            document_number=document_number,
            document_type=document_type,
            cfop=cfop,
            date_min=date_min,
            date_max=date_max,
            invoice_type=invoice_type
        )

        invoices = filter_service.filter_invoices()

        serializer = InvoiceSerializer(invoices, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=["get"], url_path="balance")
    def balance(self, request):
        document_number = request.query_params.get('document_number')
        document_type = request.query_params.get('document_type')
        cfop = request.query_params.get('cfop')
        date = request.query_params.get('date')

        if not date:
            return Response(
                {"error": "O parâmetro 'date' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        filter_service = InvoiceFilterService(
            document_number=document_number,
            document_type=document_type,
            cfop=cfop,
            date_min=None,
            date_max=date,
            invoice_type=None
        )
        invoices = filter_service.filter_invoices()

        weight_service = InvoiceWeightService(invoices)
        invoice_items = weight_service.calculate_total_weight()

        entradas = 0
        saidas = 0

        for item in invoice_items:
            if document_type == "cpf" or document_type == "cnpj":
                if (document_type == "cpf" and item.invoice.cpf_destinatario == document_number) or \
                (document_type == "cnpj" and item.invoice.cnpj_destinatario == document_number):
                    entradas += item.peso_kg

                if (document_type == "cpf" and item.invoice.cpf_emitente == document_number) or \
                (document_type == "cnpj" and item.invoice.cnpj_emitente == document_number):
                    saidas += item.peso_kg

        saldo_individual = max(0, entradas - saidas)
        saldo_total = saldo_individual

        balances = {document_number: saldo_individual} if document_number else {}
        response_data = {
            "balances": balances,
            "total_balance": saldo_total,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="balance-daily")
    def balance_daily(self, request):
        document_number = request.query_params.get('document_number')
        document_type = request.query_params.get('document_type')
        cfop = request.query_params.get('cfop')
        date_min = request.query_params.get('date_min')
        date_max = request.query_params.get('date_max')

        if not date_min or not date_max:
            return Response(
                {"error": "Os parâmetros 'date_min' e 'date_max' são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if date_min > date_max:
            return Response(
                {"error": "'date_max' deve ser posterior a 'date_min'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        date_min = datetime.strptime(date_min, "%Y-%m-%d").date()
        date_max = datetime.strptime(date_max, "%Y-%m-%d").date()

        invoices = Invoice.objects.filter(is_deleted=False)

        invoices = invoices.filter(data_emissao__gte=date_min, data_emissao__lte=date_max)

        if document_type and document_number:
            if document_type == "cpf":
                invoices = invoices.filter(
                    Q(cpf_emitente=document_number) | Q(cpf_destinatario=document_number)
                )
            elif document_type == "cnpj":
                invoices = invoices.filter(
                    Q(cnpj_emitente=document_number) | Q(cnpj_destinatario=document_number)
                )

        if cfop:
            invoices = invoices.filter(invoiceitem__cfop=cfop)

        invoice_items = InvoiceItem.objects.filter(invoice__in=invoices)

        weight_annotation = Case(
            When(unidade_comercial="SC", 
                then=F("quantidade_comercial") * 60),
            When(unidade_comercial="KG", 
                then=F("quantidade_comercial")),
            default=Value(0, output_field=FloatField()),
            output_field=FloatField(),
        )

        invoicesObj = invoices.prefetch_related(
            Prefetch('invoiceitem_set', queryset=invoice_items.annotate(peso_kg=weight_annotation), to_attr='invoiceitems')
        )

        daily_balance = {}

        current_date = date_min
        while current_date <= date_max:
            entradas = 0
            saidas = 0

            for invoice in invoicesObj:
                if invoice.data_emissao == current_date:
                    for item in invoice.invoiceitems:
                        if document_type == "cnpj" or document_type == "cpf":
                            if (document_type == "cpf" and invoice.cpf_destinatario == document_number) or \
                            (document_type == "cnpj" and invoice.cnpj_destinatario == document_number):
                                entradas += item.peso_kg

                        if document_type == "cnpj" or document_type == "cpf":
                            if (document_type == "cpf" and invoice.cpf_emitente == document_number) or \
                            (document_type == "cnpj" and invoice.cnpj_emitente == document_number):
                                saidas += item.peso_kg

            saldo_diario = max(0, entradas - saidas)

            daily_balance[current_date.strftime("%Y-%m-%d")] = saldo_diario

            current_date += timedelta(days=1)

        balances = {document_number: daily_balance} if document_number else daily_balance
        response_data = {
            "daily-balances": balances,
        }

        return Response(response_data, status=status.HTTP_200_OK)