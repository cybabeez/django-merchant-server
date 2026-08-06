from django.db import models


class SystemSettings(models.Model):
    DEFAULT_TRANSACTION_REF_REGEX = r'(?:Txn ID|Transaction ID):\s*([A-Z0-9]+)'
    DEFAULT_AMOUNT_REGEX = r'(?:UGX|KES|Ksh|Amt:)\s*([\d,]+)'

    allowed_sender_ids = models.TextField(
        blank=True,
        default='',
        help_text='Comma-separated sender IDs allowed to trigger processing, e.g. 256700000000,256700000001'
    )
    admin_allowed_ips = models.TextField(
        blank=True,
        default='127.0.0.1, ::1',
        help_text='Comma-separated IP addresses allowed to access the admin panel'
    )
    transaction_ref_regex = models.CharField(
        max_length=255,
        default=DEFAULT_TRANSACTION_REF_REGEX,
        help_text='Regex used to extract the transaction reference from an incoming SMS.'
    )
    amount_regex = models.CharField(
        max_length=255,
        default=DEFAULT_AMOUNT_REGEX,
        help_text='Regex used to extract the payment amount from an incoming SMS.'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'

    @classmethod
    def get_singleton(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @staticmethod
    def parse_csv(value):
        if not value:
            return []
        return [item.strip().replace(' ', '') for item in str(value).split(',') if item and item.strip()]

    @staticmethod
    def normalize_sender_id(sender):
        if sender is None:
            return ''
        return str(sender).strip().replace(' ', '').lstrip('+')

    @property
    def allowed_sender_id_list(self):
        return self.parse_csv(self.allowed_sender_ids)

    @property
    def admin_ip_list(self):
        return self.parse_csv(self.admin_allowed_ips)

    def is_sender_allowed(self, sender):
        normalized_sender = self.normalize_sender_id(sender)
        if not normalized_sender:
            return False
        if not self.allowed_sender_ids.strip():
            return True
        allowed = {self.normalize_sender_id(item) for item in self.allowed_sender_id_list}
        return normalized_sender in allowed

    def is_admin_ip_allowed(self, ip_address):
        if not ip_address:
            return False
        if not self.admin_allowed_ips.strip():
            return True
        candidate = str(ip_address).strip()
        allowed = {str(item).strip() for item in self.admin_ip_list}
        if candidate in allowed:
            return True
        if candidate.startswith('::ffff:'):
            ipv4 = candidate.split(':')[-1]
            return ipv4 in allowed
        return False

    def __str__(self):
        return 'System Settings'


class HotspotPlan(models.Model):
    name = models.CharField(max_length=50, help_text="e.g., 1 Hour Unlimited, Daily 1GB")
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Target payment amount in UGX")

    # RADIUSdesk Dynamic Identifiers per Plan
    radiusdesk_profile_id = models.IntegerField(
        help_text="The Profile ID in RADIUSdesk (e.g., 46)"
    )
    radiusdesk_realm_id = models.IntegerField(
        default=19,
        help_text="The Realm ID in RADIUSdesk (e.g., 19)"
    )
    radiusdesk_cloud_id = models.IntegerField(
        default=23,
        help_text="The Cloud ID in RADIUSdesk (e.g., 23)"
    )
    radiusdesk_owner_id = models.IntegerField(
        default=31,
        help_text="The Owner / User ID in RADIUSdesk (default 31 for root)"
    )

    time_limit_minutes = models.PositiveIntegerField(default=0, help_text="0 for unlimited")
    data_limit_mb = models.PositiveIntegerField(default=0, help_text="0 for unlimited")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} — UGX {self.price} (Profile: {self.radiusdesk_profile_id}, Realm: {self.radiusdesk_realm_id})"


class SMSMessage(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSED', 'Processed'),
        ('FAILED', 'Failed'),
        ('INVALID', 'Invalid/Ignored'),
    )

    sender_phone = models.CharField(max_length=20)
    raw_text = models.TextField()
    transaction_ref = models.CharField(max_length=100, blank=True, null=True, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField(blank=True, null=True)

    radiusdesk_username = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.sender_phone} ({self.status}) — {self.transaction_ref or 'No Ref'}"
