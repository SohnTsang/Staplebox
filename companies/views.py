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


class CompanyProfileView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [TemplateHTMLRenderer, JSONRenderer]
    template_name = 'companies/company_profile.html'

    def get(self, request):
        user_profile = request.user.userprofile
        try:
            company_profile = CompanyProfile.objects.get(user_profile=user_profile)
            own_profile = True  # Since the company profile corresponds to the logged-in user
        except CompanyProfile.DoesNotExist:
            context = {'company_profile': None}
            return Response(context, template_name=self.template_name, status=404)

        serializer = CompanyProfileSerializer(company_profile)
        context = {
            'company_profile': serializer.data,
            'active_page': 'Company',
            'own_profile': own_profile
        }
        return Response(context, template_name=self.template_name)


@method_decorator(login_required, name='dispatch')
class EditCompanyProfileView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'companies/company_profile_edit.html'

    def get(self, request):
        user_profile = request.user.userprofile
        company_profile, created = CompanyProfile.objects.get_or_create(user_profile=user_profile)
        form = CompanyProfileForm(instance=company_profile)  # Use the form for rendering
        return Response({'form': form}, template_name=self.template_name)

    def post(self, request):
        user_profile = request.user.userprofile
        company_profile, created = CompanyProfile.objects.get_or_create(user_profile=user_profile)
        form = CompanyProfileForm(request.POST, instance=company_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company profile updated')
            return redirect('companies:company_profile_view')
        else:
            return Response({'form': form}, template_name=self.template_name)