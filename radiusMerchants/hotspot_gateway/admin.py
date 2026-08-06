from datetime import timedelta

from django.contrib import admin
from django.db.models import Sum
from django.utils import timezone

from .models import HotspotPlan, SMSMessage, SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'allowed_sender_ids', 'admin_allowed_ips', 'updated_at')
    readonly_fields = ('updated_at',)
    fieldsets = (
        ('SMS Access Control', {
            'fields': ('allowed_sender_ids',),
            'description': 'Provide comma-separated sender IDs that are allowed to trigger payment processing.'
        }),
        ('SMS Parsing Rules', {
            'fields': ('transaction_ref_regex', 'amount_regex'),
            'description': (
                'Set the regex patterns used to capture the transaction reference and amount from incoming SMS messages. '
                'Example SMS format: "Txn ID: ABC12345 UGX 2500" or "Ref: 123ABCD Amount: UGX 2,500". '
                'For the transaction regex, capture the ID in a group like ([A-Z0-9]+). '
                'For the amount regex, capture just the numeric value like ([\\d,]+).'
            )
        }),
        ('Admin Access Control', {
            'fields': ('admin_allowed_ips',),
            'description': 'Provide comma-separated IP addresses allowed to access the Django admin panel.'
        }),
        ('Audit', {
            'fields': ('updated_at',),
        }),
    )

    def changelist_view(self, request, extra_context=None):
        if not SystemSettings.objects.exists():
            SystemSettings.get_singleton()
        return super().changelist_view(request, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        if not SystemSettings.objects.exists():
            obj = SystemSettings.get_singleton()
            return self.changeform_view(request, str(obj.pk), form_url, extra_context)
        return super().add_view(request, form_url=form_url, extra_context=extra_context)

    def has_add_permission(self, request):
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(HotspotPlan)
class HotspotPlanAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'price',
        'radiusdesk_profile_id',
        'radiusdesk_realm_id',
        'radiusdesk_cloud_id',
        'radiusdesk_owner_id',
        'is_active'
    )
    list_editable = ('is_active',)
    search_fields = ('name',)
    fieldsets = (
        ('Plan Information', {
            'fields': ('name', 'price', 'is_active')
        }),
        ('RADIUSdesk Configuration', {
            'fields': (
                'radiusdesk_profile_id',
                'radiusdesk_realm_id',
                'radiusdesk_cloud_id',
                'radiusdesk_owner_id'
            ),
            'description': 'Configure the exact RADIUSdesk Profile, Realm, Cloud, and Owner IDs for this package.'
        }),
        ('Quotas (Optional Info)', {
            'fields': ('time_limit_minutes', 'data_limit_mb')
        }),
    )


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ('transaction_ref', 'sender_phone', 'amount', 'status', 'radiusdesk_username', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender_phone', 'transaction_ref', 'raw_text')
    readonly_fields = ('created_at', 'processed_at')
    change_list_template = 'admin/hotspot_gateway/smsmessage/change_list.html'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        processed_qs = SMSMessage.objects.filter(status='PROCESSED')
        today = timezone.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_month = today.replace(day=1)

        def revenue_for(qs):
            value = qs.aggregate(Sum('amount'))['amount__sum'] or 0
            return float(value)

        extra_context['summary_stats'] = {
            'total_revenue': revenue_for(processed_qs),
            'daily_revenue': revenue_for(processed_qs.filter(processed_at__date=today)),
            'weekly_revenue': revenue_for(processed_qs.filter(processed_at__date__gte=start_of_week)),
            'monthly_revenue': revenue_for(processed_qs.filter(processed_at__date__gte=start_of_month)),
            'total_processed': processed_qs.count(),
            'total_failed': SMSMessage.objects.filter(status='FAILED').count(),
            'total_transactions': SMSMessage.objects.count(),
        }
        return super().changelist_view(request, extra_context=extra_context)
