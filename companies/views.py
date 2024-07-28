from django.shortcuts import render, redirect, get_object_or_404
from .forms import CompanyProfileForm
from .models import CompanyProfile
from django.contrib.auth.decorators import login_required
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from rest_framework.permissions import IsAuthenticated
from .serializers import CompanyProfileSerializer
from rest_framework import status
from django.utils.decorators import method_decorator
from django.contrib import messages
from .forms import CompanySelectionForm
from django.db import transaction
from django.core.signing import Signer, BadSignature

signer = Signer()


class CompanyProfileView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer, JSONRenderer]
    template_name = 'companies/company_profile.html'

    def get(self, request):
        user_profile = request.user.userprofile
        company_profile = user_profile.company_profiles.first()
        
        if company_profile:
            own_profile = True
            serializer = CompanyProfileSerializer(company_profile)
            context = {
                'company_profile': serializer.data,
                'active_page': 'Company',
                'own_profile': own_profile,
                'is_partner_profile': False  # Not a partner profile since it's the user's own profile
            }
        else:
            context = {
                'company_profile': None,
                'active_page': 'Company',
                'own_profile': False,
                'is_partner_profile': False
            }

        return Response(context, template_name=self.template_name)


@method_decorator(login_required, name='dispatch')
class EditCompanyProfileView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'companies/company_profile_edit.html'

    def get(self, request):
        user_profile = request.user.userprofile
        company_profile = user_profile.company_profiles.first()
        form = CompanyProfileForm(instance=company_profile)
        return Response({'form': form, 'company_profile': company_profile}, template_name=self.template_name)

    def post(self, request):
        user_profile = request.user.userprofile
        company_profile = user_profile.company_profiles.first() if user_profile.company_profiles.exists() else None
        form = CompanyProfileForm(request.POST, instance=company_profile)

        if form.is_valid():
            company_profile = form.save(commit=False)
            if not user_profile.company_profiles.exists():
                # New profile
                company_profile.save()
                user_profile.company_profiles.add(company_profile)
                print("Adding new profile")
            else:
                # Existing profile
                company_profile.save()
                print("Updating existing profile")
            messages.success(request, 'Company profile updated successfully.')
            return redirect('companies:company_profile_view')
        else:
            return Response({'form': form, 'company_profile': company_profile}, template_name=self.template_name)
        

@login_required
def create_company_profile(request):
    user_profile = request.user.userprofile
    if request.method == 'POST':
        form = CompanySelectionForm(request.POST)
        if form.is_valid():
            new_company_name = form.cleaned_data.get('new_company_name')
            with transaction.atomic():
                # Create a new company
                company = CompanyProfile.objects.create(name=new_company_name)
                company.user_profiles.add(user_profile)
                messages.success(request, 'Company profile created successfully.')
                return redirect('companies:company_profile_view', company_id=company.id)
    else:
        form = CompanySelectionForm()

    return render(request, 'companies/create_company.html', {'form': form})