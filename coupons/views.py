from django.utils.translation import ugettext_lazy as _
from django.http import JsonResponse
from . import models


def get_coupon_details(request):
    code = request.GET.get('code', None)
    types = request.GET.get('types', None)
    if code is None:
        data = {'err': _("Please provide a coupon code.")}
        return JsonResponse(data)
    try:
        coupon = models.Coupon.objects.get(code=code)
    except models.Coupon.DoesNotExist:
        data = {'err': _("This code is not valid.")}
        return JsonResponse(data)

    if request.user.id == 0 and coupon.user_limit is not 1:
        data = {'err': _("You must be logged in to use this coupon")}
        return JsonResponse(data)

    if coupon.is_redeemed:
        data = {'err': _("This coupon has already been redeemed")}
        return JsonResponse(data)

    try:  # check if there is a user bound coupon existing
        user_coupon = coupon.users.get(user=request.user)
        if user_coupon.redeemed_at is not None:
            data = {'err': _("You have already redeemed this coupon once.")}
            return JsonResponse(data)
    except models.CouponUser.DoesNotExist:
        if coupon.user_limit is not 0:  # zero means no limit of user count
            # only user bound coupons left and you don't have one
            if coupon.user_limit is coupon.users.filter(user__isnull=False).count():
                data = {'err': _("This code is not valid for your account.")}
                return JsonResponse(data)
            if coupon.user_limit is coupon.users.filter(redeemed_at__isnull=False).count():  # all coupons redeemed
                data = {'err': _("This code has already been used.")}
                return JsonResponse(data)
    if types is not None and coupon.type not in types:
        data = {'err': _("This code is not meant to be used here.")}
        return JsonResponse(data)
    if coupon.expired():
        data = {'err': _("This code is expired.")}
        return JsonResponse(data)
    data = {
        'code': coupon.code,
        'value': coupon.value,
        'type': coupon.type,
    }
    return JsonResponse(data)
