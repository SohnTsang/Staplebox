from django.shortcuts import render, redirect, get_object_or_404
from .forms import CompanyProfileForm
from .models import CompanyProfile
from django.contrib.auth.decorators import login_required
from partners.models import Partnership  # Assuming your Partnership model is in partnerships/models.py



@login_required
def company_profile_view(request):
    user_profile = request.user.userprofile
    try:
        company_profile = CompanyProfile.objects.get(user_profile=user_profile)
        own_profile = True  # Since the company profile corresponds to the logged-in user
    except CompanyProfile.DoesNotExist:
        context = {'company_profile': None}
        return render(request, 'companies/company_profile.html', context)

    context = {
        'company_profile': company_profile,
        'active_page': 'Company',
        'own_profile': own_profile  # Pass this to the template
    }

    return render(request, 'companies/company_profile.html', context)


@login_required
def edit_company_profile(request):
    
    user_profile = request.user.userprofile
    # Try to get the CompanyProfile, or set to None if it doesn't exist
    company_profile, created = CompanyProfile.objects.get_or_create(user_profile=user_profile)
    
    if request.method == 'POST':
        form = CompanyProfileForm(request.POST, instance=company_profile)
        if form.is_valid():
            company_name = form.cleaned_data['name']
            company_email = form.cleaned_data.get('email', None)
            company_profile.phone_number = form.cleaned_data['phone_number']
            
            if CompanyProfile.objects.exclude(id=company_profile.id).filter(name=company_name).exists():
                form.add_error('name', 'A company with this name already exists.')
            else:
                form.save()
                return redirect('companies:company_profile_view')
    else:
        form = CompanyProfileForm(instance=company_profile)
        

    # If a new profile was created by get_or_create, it's technically an edit page but will function as a create page.
    return render(request, 'companies/company_profile_edit.html', {'form': form})