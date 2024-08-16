from django.db.models import Q
from partners.models import Partnership
from companies.models import CompanyProfile  # Adjust the import based on your actual models

def get_partner_info(user, filter_value='', sort_by='created_at', search_query=''):
    partner_info = []

    # Get the user's company profiles
    user_company_profiles = CompanyProfile.objects.filter(user_profiles__user=user)

    if not user_company_profiles.exists():
        return partner_info

    # Construct the query to filter partnerships where the user's company profile is either partner1 or partner2
    query = Q(partner1__in=user_company_profiles) | Q(partner2__in=user_company_profiles)
    query &= Q(is_active=True)

    # Apply search criteria if provided
    if search_query:
        query &= (Q(partner2__name__icontains=search_query) |
                  Q(partner1__name__icontains=search_query))

    partnerships = Partnership.objects.filter(query).distinct()

    for partnership in partnerships:
        partner = partnership.partner2 if partnership.partner1 in user_company_profiles else partnership.partner1
        partner_dict = {
            'company_name': partner.name,
            'company_role': partner.role,
            'company_email': partner.email,  # Assuming email is a field in the CompanyProfile
            'created_at': partnership.created_at.strftime('%Y-%m-%d'),
            'partner_id': partner.uuid,  # Assuming `uuid` is the unique identifier
        }
        partner_info.append(partner_dict)

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