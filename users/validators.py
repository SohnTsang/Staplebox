from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import re

class ValidateNotSameAsOldPassword:
    def validate(self, password, user=None):
        if user and user.check_password(password):
            raise ValidationError(
                _("Your new password cannot be the same as your old password."),
                code='password_no_change',
            )

    def get_help_text(self):
        return _("Your new password cannot be the same as your old password.")
    

class CustomPasswordValidator:
    def validate(self, password, user=None):
        errors = []

        if len(password) < 8:
            errors.append(ValidationError(
                _("The password must be at least 8 characters long."),
                code='password_too_short',
            ))
        if not re.search(r'[A-Z]', password):
            errors.append(ValidationError(
                _("The password must contain at least 1 uppercase letter."),
                code='password_no_upper',
            ))
        if not re.search(r'[a-z]', password):
            errors.append(ValidationError(
                _("The password must contain at least 1 lowercase letter."),
                code='password_no_lower',
            ))

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Your password must be at least 8 characters long and contain at least one uppercase letter and one lowercase letter."
        )
    