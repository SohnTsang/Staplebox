from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Export, ExportProduct, ExportDocument
from products.models import Product
from folder.models import Folder
from documents.models import Document
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from partners.models import Partnership
from django.db.models import Q
from django.contrib.auth.models import User


@login_required
def export_list(request):
    # Fetching all exports for active partnerships where the current user is involved
    partnerships = Partnership.objects.filter(
        Q(partner1=request.user) | Q(partner2=request.user),
        is_active=True
    ).select_related(
        'partner1__userprofile__companyprofile', 'partner2__userprofile__companyprofile'
    )
    user_exports = Export.objects.filter(
        partner__in=Partnership.objects.filter(
            Q(partner1=request.user) | Q(partner2=request.user),
            is_active=True
        )
    ).prefetch_related('export_products__product', 'partner')

    return render(request, 'exports/export_list.html', {'exports': user_exports, 'partnerships': partnerships})


@login_required
def list_products(request):
    products = Product.objects.filter(user=request.user)
    products_data = [{'id': product.id, 'code': product.product_code, 'name': product.product_name} for product in products]
    return JsonResponse({'products': products_data})


@login_required
def list_partners(request):
    # Get the current user
    user = request.user
    # Query partnerships where the user is involved either as partner1 or partner2
    partnerships = Partnership.objects.filter(
        Q(partner1=user) | Q(partner2=user), is_active=True
    )
    
    # Build a list of partner data
    partners = []
    for partnership in partnerships:
        # Add partner2 if the current user is partner1, otherwise add partner1
        partner = partnership.partner2 if partnership.partner1 == user else partnership.partner1
        partners.append({'id': partner.id, 'name': partner.username})  # Assuming partner has a username field

    return JsonResponse({'partners': partners})


@login_required
def create_export(request):
    if request.method == 'POST':
        export_date_str = request.POST.get('export_date')
        partner_id = request.POST.get('partner_id')
        export_date = parse_date(export_date_str)
        # Correctly filtering the partnership
        partnership = Partnership.objects.filter(
            Q(partner1_id=partner_id, partner2=request.user) |
            Q(partner2_id=partner_id, partner1=request.user),
            is_active=True
        ).first()

        if not partnership:
            return JsonResponse({'success': False, 'error': 'No valid partnership found.'}, status=404)

        if export_date is not None:
            export = Export.objects.create(export_date=export_date, created_by=request.user, partner=partnership)
            is_current_user_partner1 = (partnership.partner1 == request.user)
            return JsonResponse({
                'success': True,
                'export_id': export.id,
                'export_date': export.export_date.strftime('%Y-%m-%d'),
                'partner_name': partnership.partner2.userprofile.companyprofile.name if is_current_user_partner1 else partnership.partner1.userprofile.companyprofile.name,
                'is_current_user_partner1': is_current_user_partner1
            })
        else:
            return JsonResponse({'success': False, 'error': 'Invalid date.'}, status=400)

    return JsonResponse({'success': False, 'error': 'Only POST method is allowed.'}, status=405)


@login_required
def add_product_to_export(request, export_id):
    if request.method == 'POST':
        export = get_object_or_404(Export, id=export_id, created_by=request.user)
        product_id = request.POST.get('product_id')
        product = get_object_or_404(Product, id=product_id)
        export_product = ExportProduct.objects.create(export=export, product=product)
        return JsonResponse({'success': True, 'export_product_id': export_product.id, 'product_name': product.product_name, 'product_code':product.product_code})
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def upload_document_to_partner(request, export_partner_id):
    """API endpoint to upload documents for a partner in an export context."""
    export_partner = get_object_or_404(ExportPartner, id=export_partner_id)
    documents_data = []
    if request.method == 'POST' and 'document_files' in request.FILES:
        for file in request.FILES.getlist('document_files'):
            document = Document.objects.create(file=file, folder=export_partner.folder, uploaded_by=request.user)
            export_document = ExportDocument.objects.create(export_partner=export_partner, document=document)
            documents_data.append({'document_id': document.id, 'file_name': document.file.name})
        return JsonResponse({'success': True, 'documents': documents_data})
    return JsonResponse({'success': False, 'error': 'No files uploaded'}, status=400)


@login_required
@require_POST
def delete_export(request, export_id):
    export = get_object_or_404(Export, id=export_id, created_by=request.user)
    export.delete()
    return JsonResponse({'success': True})