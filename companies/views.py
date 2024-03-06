from django.shortcuts import render, redirect, get_object_or_404
from .forms import CompanyProfileForm
from .models import CompanyProfile
from django.contrib.auth.decorators import login_required

@login_required
def company_profile_view(request):
    user_profile = request.user.userprofile
    try:
        company_profile = CompanyProfile.objects.get(user_profile=user_profile)
    except CompanyProfile.DoesNotExist:
        # If no CompanyProfile exists, render a different template or pass a flag to the template
        # Indicating that the profile does not exist and perhaps a link/button to create one.
        context = {'company_profile': None}
        return render(request, 'companies/company_profile.html', context)

    context = {'company_profile': company_profile}
    return render(request, 'companies/company_profile.html', context)


@login_required
def edit_company_profile(request):
    user_profile = request.user.userprofile
    # Try to get the CompanyProfile, or set to None if it doesn't exist
    company_profile, created = CompanyProfile.objects.get_or_create(user_profile=user_profile)
    
    if request.method == 'POST':
        form = CompanyProfileForm(request.POST, instance=company_profile)
        if form.is_valid():
            form.save()
            # Redirect to the company profile view after the profile is updated or created
            return redirect('company_profile_view')
    else:
        form = CompanyProfileForm(instance=company_profile)

    # If a new profile was created by get_or_create, it's technically an edit page but will function as a create page.
    return render(request, 'companies/company_profile_edit.html', {'form': form})