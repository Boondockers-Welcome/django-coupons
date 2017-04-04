from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^get-coupon-details/$', views.get_coupon_details, name='get-coupon-details'),
]
