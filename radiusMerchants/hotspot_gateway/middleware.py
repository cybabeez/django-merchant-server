from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .models import SystemSettings


class AdminIPRestrictionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            ip_address = request.META.get('REMOTE_ADDR') or request.META.get('HTTP_X_FORWARDED_FOR')
            system_settings = SystemSettings.get_singleton()
            if not system_settings.is_admin_ip_allowed(ip_address):
                messages.error(request, 'Access to the admin panel is restricted to approved IP addresses.')
                return HttpResponseForbidden('Admin access denied from this IP address.')
        return self.get_response(request)
