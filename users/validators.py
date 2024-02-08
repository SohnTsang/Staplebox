from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class ValidateNotSameAsOldPassword:
    def validate(self, password, user=None):
        if not user:
            return
        if user.check_password(password):
            raise ValidationError(
                _("Your new password cannot be the same as your old password."),
                code='password_no_change',
            )

    def get_help_text(self):
        return _("Your new password cannot be the same as your old password.")