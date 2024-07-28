from django.db.models import Q
from partners.models import Partnership
from companies.models import CompanyProfile  # Adjust the import based on your actual models

def get_partner_info(user, filter_value='', sort_by='created_at', search_query=''):
    partner_info = []
    query = Q(partner1=user) | Q(partner2=user)
    query &= Q(is_active=True)

    # Apply search criteria if provided
    if search_query:
        query &= (Q(partner2__userprofile__company_profiles__name__icontains=search_query) |
                  Q(partner1__userprofile__company_profiles__name__icontains=search_query) |
                  Q(partner2__email__icontains=search_query) |
                  Q(partner1__email__icontains=search_query))

    partnerships = Partnership.objects.filter(query).distinct()

    for partnership in partnerships:
        partner = partnership.partner2 if partnership.partner1 == user else partnership.partner1
        try:
            profile = CompanyProfile.objects.get(user_profiles=partner.userprofile)
            partner_dict = {
                'company_name': profile.name,
                'company_role': profile.role,
                'company_email': partner.email,
                'created_at': partnership.created_at.strftime('%Y-%m-%d'),
                'partner_id': partner.id,  # This will be used for sorting
            }
            partner_info.append(partner_dict)
        except CompanyProfile.DoesNotExist:
            # Handle case where profile does not exist
            continue

    # Apply filtering after collecting data if a filter value is provided
    if filter_value:
        partner_info = [info for info in partner_info if filter_value.lower() in info['company_name'].lower()]
    # Sorting
    if sort_by == 'company_name':
        # Sort the partner_info list by 'company_name'. This is Python-side sorting.
        partner_info.sort(key=lambda x: x['company_name'].lower())
    else:
        # Default sorting by 'created_at'. Adjust as needed for datetime fields.
        partner_info.sort(key=lambda x: x['created_at'], reverse=True)  # Assuming you want the most recent first

    return partner_info


