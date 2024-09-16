from django.db.models import Q
from partners.models import Partnership
from companies.models import CompanyProfile  # Adjust the import based on your actual models
from django.core.signing import Signer, BadSignature

signer = Signer()

def get_partner_info(company_profile, filter_value='', sort_by='created_at', search_query=''):
    partner_info = []

    # Construct the query to filter partnerships where the company's profile is either partner1 or partner2
    query = Q(partner1=company_profile) | Q(partner2=company_profile)
    query &= Q(is_active=True)

    # Apply search criteria if provided
    if search_query:
        query &= (Q(partner2__name__icontains=search_query) |
                  Q(partner1__name__icontains=search_query))

    partnerships = Partnership.objects.filter(query).distinct()

    for partnership in partnerships:
        partner = partnership.partner2 if partnership.partner1 == company_profile else partnership.partner1
        # Sign the partner UUID
        signed_partner_uuid = signer.sign(str(partner.uuid))
        partner_dict = {
            'company_name': partner.name,
            'company_role': partner.role,
            'company_email': partner.email,
            'created_at': partnership.created_at.strftime('%Y-%m-%d'),
            'partner_id': signed_partner_uuid,  # Use signed UUID
        }
        partner_info.append(partner_dict)

    # Apply filtering after collecting data if a filter value is provided
    if filter_value:
        partner_info = [info for info in partner_info if filter_value.lower() in info['company_name'].lower()]

    # Sorting
    if sort_by == 'company_name':
        partner_info.sort(key=lambda x: x['company_name'].lower())
    else:
        partner_info.sort(key=lambda x: x['created_at'], reverse=True)  # Assuming you want the most recent first

    return partner_info
