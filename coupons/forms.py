from django import forms
from django.utils.translation import ugettext_lazy as _

from .models import Coupon, CouponUser, Campaign
from .settings import COUPON_TYPES, PRODUCT_MODEL, PRODUCT_NAME_FIELD


class CouponGenerationForm(forms.Form):
    quantity = forms.IntegerField(label=_("Quantity"))
    value = forms.IntegerField(label=_("Value"))
    type = forms.ChoiceField(label=_("Type"), choices=COUPON_TYPES)
    valid_until = forms.SplitDateTimeField(
        label=_("Valid until"), required=False,
        help_text=_("Leave empty for coupons that never expire")
    )
    prefix = forms.CharField(label="Prefix", required=False)
    campaign = forms.ModelChoiceField(
        label=_("Campaign"), queryset=Campaign.objects.all(), required=False
    )


class CouponForm(forms.Form):
    code = forms.CharField(label=_("Coupon code"), required=False)

    def __init__(self, *args, **kwargs):
        self.user = None
        self.types = None
        self.products = None
        if 'user' in kwargs:
            self.user = kwargs['user']
            del kwargs['user']
        if 'types' in kwargs:
            self.types = kwargs['types']
            del kwargs['types']
        if 'products' in kwargs:
            self.products = kwargs['products']
            del kwargs['products']
        super(CouponForm, self).__init__(*args, **kwargs)

    def clean_code(self):
        code = self.cleaned_data['code']
        if not code:
            return code
        try:
            coupon = Coupon.objects.get_coupon(code)
        except Coupon.DoesNotExist:
            raise forms.ValidationError(_("This code is not valid."))
        self.coupon = coupon

        if self.user is None and coupon.user_limit > 1:
            # coupons with can be used only once can be used without tracking the user, otherwise there is no chance
            # of excluding an unknown user from multiple usages.
            raise forms.ValidationError(_(
                "The server must provide an user to this form to allow you to use this code. Maybe you need to sign in?"
            ))

        if not coupon.active:
            raise forms.ValidationError(_("This code is not active."))

        if coupon.is_redeemed:
            raise forms.ValidationError(_("This code has already been used."))

        try:  # check if there is a user bound coupon existing
            user_coupon = coupon.users.get(user=self.user)
            if user_coupon.redeemed_at is not None:
                raise forms.ValidationError(_("This code has already been used by your account."))
        except CouponUser.DoesNotExist:
            if coupon.user_limit is not 0:  # zero means no limit of user count
                if not coupon.bulk:
                    # only user bound coupons left and you don't have one
                    if coupon.user_limit is coupon.users.filter(user__isnull=False).count():
                        raise forms.ValidationError(_("This code is not valid for your account."))
                    # all coupons redeemed
                    if coupon.user_limit is coupon.users.filter(redeemed_at__isnull=False).count():
                        raise forms.ValidationError(_("This code has already been used."))
                else:
                    if coupon.users.filter(code=code).exists():
                        raise forms.ValidationError(_("This code has already been used."))
                    if coupon.bulk_number is coupon.users.filter(user__isnull=False).count():
                        raise forms.ValidationError(_("This code is not valid for your account."))
        if self.types is not None and coupon.type not in self.types:
            raise forms.ValidationError(_("This code is not meant to be used here."))
        if coupon.expired():
            raise forms.ValidationError(_("This code is expired."))
        if PRODUCT_MODEL is not None and coupon.valid_products.count() > 0:
            applicable_products = []
            for valid_product in coupon.valid_products.all():
                product_name = getattr(valid_product, PRODUCT_NAME_FIELD)
                if product_name in self.products:
                    applicable_products.append(product_name)
            if len(applicable_products) == 0:
                raise forms.ValidationError(_("This code is not valid for the product selected."))
        return code
