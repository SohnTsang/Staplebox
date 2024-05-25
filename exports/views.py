from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import Export, ExportProduct, ExportDocument, PartnerExport, StagedPartner
from products.models import Product
from documents.models import Document
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from partners.models import Partnership
from django.db.models import Q
import datetime
from django.db.models import Max
from django.db.models import Prefetch
from django.db import transaction
from django.shortcuts import get_list_or_404



def generate_reference_number(partner_id, export_date):
    partner_id = int(partner_id)  # Ensure partner_id is an integer
    export_date_str = export_date.strftime('%Y%m%d')  # Use the export date provided by the user
    partner_hex = f'{partner_id:05X}'  # Convert partner ID to hexadecimal and pad to 5 digits
    prefix = f'EXP{export_date_str}'
    ref_prefix = f'{prefix}{partner_hex}'

    last_number = Export.objects.filter(reference_number__startswith=ref_prefix).aggregate(Max('reference_number'))['reference_number__max']

    if last_number:
        hex_seq = last_number[len(ref_prefix):]
        last_seq_number = int(hex_seq, 16) + 1
    else:
        last_seq_number = 1

    new_ref_number = f"{ref_prefix}{last_seq_number:05X}"
    return new_ref_number



@login_required
def export_list(request):
    user = request.user
    partnerships = Partnership.objects.filter(
        Q(partner1=user) | Q(partner2=user),
        is_active=True
    ).select_related(
        'partner1__userprofile__companyprofile', 'partner2__userprofile__companyprofile'
    )

    staged_partners = StagedPartner.objects.filter(user=user).select_related('partner__userprofile__companyprofile')

    user_exports = Export.objects.filter(created_by=user).prefetch_related(
        Prefetch('partner_exports', queryset=PartnerExport.objects.prefetch_related(
            Prefetch('export_documents', queryset=ExportDocument.objects.select_related('document')),
            'partner__partner1__userprofile__companyprofile',
            'partner__partner2__userprofile__companyprofile'
        ))
    )

    all_partners = []

    for staged in staged_partners:
        all_partners.append({
            'partner_name': staged.partner.userprofile.companyprofile.name,
            'partner_company_type': staged.partner.userprofile.companyprofile.role,
            'staged_partner_id': staged.id,
            'partner_id': staged.partner.id,
            'partner_exports': [],
        })

    for export in user_exports:

        for partner_export in export.partner_exports.all():
            if partner_export.partner.partner1 == user:
                partner_name = partner_export.partner.partner2.userprofile.companyprofile.name
                partner_id = partner_export.partner.partner2.id
            else:
                partner_name = partner_export.partner.partner1.userprofile.companyprofile.name
                partner_id = partner_export.partner.partner1.id

            documents = [
                {
                    'document_id': doc.document.id,
                    'file_name': doc.document.original_filename,
                    'created_at': doc.document.created_at,
                    'comment': doc.document.comments,
                }
                for doc in partner_export.export_documents.all()
            ]
            partner_export.documents = documents
            partner_export.partner_name = partner_name

            for partner in all_partners:
                if partner['partner_name'] == partner_name:
                    partner['partner_exports'].append(partner_export)
                    break
            else:
                all_partners.append({
                    'partner_name': partner_name,
                    'staged_partner_id': None,
                    'partner_id': partner_id,
                    'partner_exports': [partner_export],
                })
            

    return render(request, 'exports/export_list.html', {
        'all_partners': all_partners,
        'partnerships': partnerships,
    })


@login_required
def get_export_dates(request, partner_id):
    try:
        # Retrieve all active partnerships involving this user
        partnerships = Partnership.objects.filter(
            Q(partner1_id=partner_id) | Q(partner2_id=partner_id),
            is_active=True
        )

        # Fetch related exports for these partnerships
        partner_exports = PartnerExport.objects.filter(
            partner__in=partnerships
        ).select_related('export').order_by('-export_date')

        # Prepare data for response
        exports_data = [{
            'id': pe.id,
            'export_id': pe.export.id,
            'date': pe.export.export_date.strftime('%Y-%m-%d') if pe.export.export_date else 'Date not set',
            'reference_number': pe.export.reference_number
        } for pe in partner_exports]

        # Return JSON response with the data
        if exports_data:
            return JsonResponse({'exports': exports_data})
        else:
            return JsonResponse({'message': f'No exports found for this user'}, status=404)

    except Exception as e:
        # Log and return the error
        print(f"Error during getting export dates: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    

@login_required
def get_export_documents(request, partner_export_id):
    try:
        partner_export = PartnerExport.objects.get(id=partner_export_id)
        documents = ExportDocument.objects.filter(partner_export=partner_export).select_related('document')
        documents_data = [{
            'id': doc.id,
            'document_id': doc.document_id,
            'filename': doc.document.file_name,
            'uploaded_on': doc.document.created_at.strftime('%Y-%m-%d')  # Using `created_at` instead of `uploaded_at`
        } for doc in documents]

        if documents_data:
            return JsonResponse({'documents': documents_data})
        else:
            return JsonResponse({'message': 'No documents found for this export'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

@login_required
def list_products(request):
    products = Product.objects.filter(user=request.user)
    products_data = [{'id': product.id, 'code': product.product_code, 'name': product.product_name} for product in products]
    return JsonResponse({'products': products_data})


@login_required
def list_partners(request):
    user = request.user
    partnerships = Partnership.objects.filter(
        Q(partner1=user) | Q(partner2=user), is_active=True
    ).select_related('partner1__userprofile__companyprofile', 'partner2__userprofile__companyprofile')

    partners = []
    for partnership in partnerships:
        if partnership.partner1 == user:
            partner_info = {
                'id': partnership.partner2.id,
                'name': partnership.partner2.userprofile.companyprofile.name  # Ensure this path is correct
            }
        else:
            partner_info = {
                'id': partnership.partner1.id,
                'name': partnership.partner1.userprofile.companyprofile.name  # Ensure this path is correct
            }
        partners.append(partner_info)

    return JsonResponse({'partners': partners})


@login_required
def add_partner_to_staging(request):
    if request.method == 'POST':
        partner_ids = request.POST.getlist('partner_ids')
        response_data = []
        user = request.user

        for partner_id in partner_ids:
            partner, created = StagedPartner.objects.get_or_create(user=user, partner_id=partner_id)
            response_data.append({
                'partner_id': partner_id,
                'partner_name': partner.partner.username,  # assuming using username
                'status': 'added' if created else 'already staged'
            })

        return JsonResponse({'success': True, 'partners': response_data})


@login_required
@require_POST
def create_export_with_date(request):
    export_date_str = request.POST.get('export_date')
    export_date = parse_date(export_date_str)
    staged_partner_id = request.POST.get('staged_partner_id')
    partner_id = int(request.POST.get('partner_id'))

    # Find the appropriate partnership
    if staged_partner_id and staged_partner_id != 'null':
        staged_partner = get_object_or_404(StagedPartner, id=staged_partner_id, user=request.user)
        partnership = Partnership.objects.filter(
            Q(partner1=request.user, partner2=staged_partner.partner) | Q(partner2=request.user, partner1=staged_partner.partner),
            is_active=True
        ).first()
    else:
        partnership = Partnership.objects.filter(
            Q(partner1=request.user, partner2_id=partner_id) | Q(partner2=request.user, partner1_id=partner_id),
            is_active=True
        ).first()

    if not partnership:
        return JsonResponse({'success': False, 'error': 'No valid partnership found.'}, status=400)

    # Check if an export for this partner on this date already exists
    existing_export = PartnerExport.objects.filter(partner=partnership, export__export_date=export_date).exists()
    if existing_export:
        return JsonResponse({'success': False, 'error': 'An export for this partner on this date already exists'}, status=409)

    # Create the export
    export = Export.objects.create(
        created_by=request.user,
        export_date=export_date,
        reference_number=generate_reference_number(partner_id, export_date)
    )
    
    PartnerExport.objects.create(
        partner=partnership,
        export=export,
        export_date=export_date
    )
    
    return JsonResponse({
        'success': True,
        'export_id': export.id,
        'export_date': export.export_date.strftime('%Y-%m-%d'),
        'reference_number': export.reference_number
    })


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
@require_POST
@transaction.atomic
def delete_partners(request):
    # Retrieve lists of IDs from the request
    staged_partner_ids = request.POST.get('staged_partner_ids', '').split(',')
    partner_ids = request.POST.get('partner_ids', '').split(',')


    try:
        # Delete each staged partner based on provided IDs
        staged_partner_ids = [int(id) for id in staged_partner_ids if id]
        partner_ids = [int(id) for id in partner_ids if id]

        if staged_partner_ids and staged_partner_ids[0] != 'null':
            StagedPartner.objects.filter(id__in=staged_partner_ids).delete()


        # Handle deletions of partner exports related to each partner ID
        if partner_ids:
            # Filter partnerships where the current user is part of the partnership and the other partner is in the list
            partnerships = Partnership.objects.filter(
                (Q(partner1=request.user, partner2_id__in=partner_ids) |
                 Q(partner2=request.user, partner1_id__in=partner_ids)),
                is_active=True
            )
            # Delete associated partner exports and their documents
            for partnership in partnerships:
                partner_exports = PartnerExport.objects.filter(partner=partnership)
                for partner_export in partner_exports:
                    ExportDocument.objects.filter(partner_export=partner_export).delete()
                    partner_export.delete()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

@login_required
@require_POST
@transaction.atomic
def delete_exports(request):
    export_ids = request.POST.get('export_ids', '')
    export_ids = export_ids.split(',') if export_ids else []
    # Ensure that export_ids are integers
    try:
        export_ids = [int(id) for id in export_ids]
        exports = Export.objects.filter(id__in=export_ids, created_by=request.user)
        exports.delete()
        return JsonResponse({'success': True, 'message': 'Exports deleted successfully.'})
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid export IDs provided.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

    

@login_required
@require_POST
@transaction.atomic
def delete_documents(request):
    document_ids = request.POST.get('document_ids', '').split(',')
    document_ids = [int(id) for id in document_ids if id.isdigit()]

    print(document_ids)
    try:
        documents = get_list_or_404(Document, id__in=document_ids, document_exports__partner_export__export__created_by=request.user)
        count, _ = Document.objects.filter(id__in=[doc.id for doc in documents]).delete()
        return JsonResponse({'success': True, 'message': f'Deleted {count} documents successfully.'})
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Invalid document IDs provided.'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})