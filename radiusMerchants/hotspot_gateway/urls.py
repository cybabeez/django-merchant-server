from django.urls import path
from .views import gammu_incoming_sms

urlpatterns = [
    path('api/sms/incoming/', gammu_incoming_sms, name='gammu_incoming_sms'),
]