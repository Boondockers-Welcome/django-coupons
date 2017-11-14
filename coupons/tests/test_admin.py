from distutils.version import StrictVersion
from unittest import skipIf

import django
from django.test import TestCase
from django.contrib.admin.sites import AdminSite

from coupons.admin import CouponAdmin
from coupons.models import Coupon
from coupons import settings


class MockRequest(object):
    pass


request = MockRequest()


class CouponAdminTestCase(TestCase):
    def setUp(self):
        self.site = AdminSite()

    @skipIf(StrictVersion(django.get_version()) < StrictVersion('1.7'), "Skip list display test due to missing method.")
    def test_list_display(self):
        admin = CouponAdmin(Coupon, self.site)

        fields = [
            'code', 'description', 'value', 'type', 'user_limit', 'created_at', 'valid_until', 'active',
            'campaign', 'bulk', 'bulk_number', 'bulk_seed', 'bulk_length'
        ]

        if settings.PRODUCT_MODEL:
            fields.append('valid_products')

        self.assertEquals(list(admin.get_fields(request)), fields)
