from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from .models import UserProfile
from allauth.account.models import EmailAddress
from companies.models import CompanyProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'UserProfile'
    fk_name = 'user'

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline, )
    list_display = ('username', 'email', 'company_name', 'is_staff', 'is_active', 'date_joined', 'last_login', 'get_verified')
    list_select_related = ('userprofile', )

    def company_name(self, obj):
        """Retrieve company name from the CompanyProfile model."""
        profile = CompanyProfile.objects.filter(user_profiles__user=obj).first()
        return profile.name if profile else None

    company_name.short_description = "Company Name"  # Optional: Sets column name

    def get_verified(self, instance):
        # Check if there is a verified email for the user
        return EmailAddress.objects.filter(user=instance, verified=True).exists()
    get_verified.short_description = 'Verified?'
    get_verified.boolean = True

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(UserAdmin, self).get_inline_instances(request, obj)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)
