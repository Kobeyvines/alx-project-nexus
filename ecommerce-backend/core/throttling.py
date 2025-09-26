"""Custom throttling classes for rate limiting."""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle


class BurstRateThrottle(UserRateThrottle):
    """
    Throttle for burst requests (high rate for a short period).
    Useful for API endpoints that might be called rapidly but should be limited.
    """
    scope = 'burst'
    rate = '60/minute'


class SustainedRateThrottle(UserRateThrottle):
    """
    Throttle for sustained requests (lower rate over a longer period).
    Useful for more resource-intensive operations.
    """
    scope = 'sustained'
    rate = '1000/day'


class AuthRateThrottle(AnonRateThrottle):
    """
    Specific throttle for authentication-related endpoints.
    More restrictive to prevent brute force attempts.
    """
    scope = 'auth'
    rate = '5/minute'


class OrderRateThrottle(UserRateThrottle):
    """
    Specific throttle for order-related endpoints.
    Prevents abuse of order creation and manipulation.
    """
    scope = 'orders'
    rate = '100/day'