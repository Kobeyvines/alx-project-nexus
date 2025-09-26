"""Custom password validators for enhanced security."""
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class PasswordComplexityValidator:
    """
    Validate password complexity requirements:
    - Minimum length of 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """

    def __init__(self, min_length=8):
        self.min_length = min_length

    def validate(self, password, user=None):
        if len(password) < self.min_length:
            raise ValidationError(
                _(f"Password must be at least {self.min_length} characters long."),
                code='password_too_short',
            )
        
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter."),
                code='password_no_upper',
            )
            
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter."),
                code='password_no_lower',
            )
            
        if not re.search(r'[0-9]', password):
            raise ValidationError(
                _("Password must contain at least one digit."),
                code='password_no_digit',
            )
            
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValidationError(
                _("Password must contain at least one special character: !@#$%^&*(),.?\":{}|<>"),
                code='password_no_symbol',
            )

    def get_help_text(self):
        return _(
            "Your password must contain at least %(min_length)d characters, "
            "including uppercase and lowercase letters, digits, and special characters."
        ) % {'min_length': self.min_length}


class UserAttributeSimilarityValidator:
    """
    Validate that the password is not too similar to user attributes.
    """
    
    def validate(self, password, user=None):
        if not user:
            return

        # Check username similarity
        if user.username.lower() in password.lower():
            raise ValidationError(
                _("Password cannot contain your username."),
                code='password_contains_username',
            )

        # Check email similarity
        if user.email:
            email_name = user.email.split('@')[0]
            if email_name.lower() in password.lower():
                raise ValidationError(
                    _("Password cannot contain your email address."),
                    code='password_contains_email',
                )

    def get_help_text(self):
        return _("Your password cannot be too similar to your other personal information.")