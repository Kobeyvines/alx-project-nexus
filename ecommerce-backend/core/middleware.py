"""
Custom middleware for request validation and sanitization.
"""
import json
import bleach
from django.http import JsonResponse
from django.core.exceptions import ValidationError
import logging

logger = logging.getLogger(__name__)

class RequestValidationMiddleware:
    """
    Middleware for validating and sanitizing incoming requests.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip validation for non-API requests
        if not request.path.startswith('/api/'):
            return self.get_response(request)

        try:
            # Validate and sanitize request data
            self.validate_request(request)
            response = self.get_response(request)
            return response
        except ValidationError as e:
            logger.warning(f"Request validation failed: {str(e)}")
            return JsonResponse({
                'error': 'Invalid request data',
                'details': str(e)
            }, status=400)
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON format'
            }, status=400)
        except Exception as e:
            logger.error(f"Unexpected error in request validation: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error'
            }, status=500)

    def validate_request(self, request):
        """
        Validate and sanitize the request data.
        """
        # Validate content type for POST/PUT/PATCH requests
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.headers.get('Content-Type', '')
            if not content_type.startswith('application/json'):
                raise ValidationError('Content-Type must be application/json')

            # Parse and validate JSON data
            if request.body:
                try:
                    data = json.loads(request.body)
                    sanitized_data = self.sanitize_data(data)
                    # Replace request body with sanitized data
                    request._body = json.dumps(sanitized_data).encode('utf-8')
                except json.JSONDecodeError:
                    raise ValidationError('Invalid JSON format')

        # Validate query parameters
        if request.GET:
            sanitized_get = {
                key: self.sanitize_value(value)
                for key, value in request.GET.items()
            }
            request.GET = request.GET.copy()
            request.GET.clear()
            request.GET.update(sanitized_get)

    def sanitize_data(self, data):
        """
        Recursively sanitize data structure.
        """
        if isinstance(data, dict):
            return {key: self.sanitize_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_data(item) for item in data]
        elif isinstance(data, str):
            return self.sanitize_value(data)
        return data

    def sanitize_value(self, value):
        """
        Sanitize a single value.
        """
        if not isinstance(value, str):
            return value
        
        # Clean HTML content if present
        cleaned = bleach.clean(
            value,
            tags=[],  # No HTML tags allowed
            strip=True
        )
        
        # Basic XSS protection
        cleaned = cleaned.replace('&lt;script&gt;', '')
        cleaned = cleaned.replace('&lt;/script&gt;', '')
        
        return cleaned