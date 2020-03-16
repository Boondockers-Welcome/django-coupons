from django.conf.urls import url
from django.contrib import admin
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.views.generic.base import TemplateView
from django import urls
from .forms import CouponGenerationForm
from .models import Coupon, CouponUser, Campaign
from . import settings


class CouponUserInline(admin.TabularInline):
    model = CouponUser
    extra = 0
    raw_id_fields_list = ['user']
    if settings.ORDER_MODEL:
        raw_id_fields_list.append('order')
    raw_id_fields = tuple(raw_id_fields_list)

    def get_max_num(self, request, obj=None, **kwargs):
        if obj:
            return obj.user_limit
        return None  # disable limit for new objects (e.g. admin add)


class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'code', 'type', 'value', 'user_count', 'user_limit', 'is_redeemed', 'valid_until', 'campaign'
    ]
    list_filter = ['type', 'campaign', 'created_at', 'valid_until']
    raw_id_fields = ()
    search_fields = ('code', 'value')
    inlines = (CouponUserInline,)
    exclude = ('users',)
    ordering = ['-created_at']

    readonly_fields = ('gift_certificate_order',)

    def gift_certificate_order(self, obj):
        order = obj.productlineitem_set.first().order
        link = urls.reverse(
            "admin:purchases_order_change",
            args=[order.id]
        )
        return u'<a href="%s">%s by %s on %s</a>' % (
            link,
            order.id,
            order.user.username,
            order.timestamp.date(),
        )

    def user_count(self, inst):
        return inst.users.count()

    def get_urls(self):
        urls = super(CouponAdmin, self).get_urls()
        my_urls = [
            url(r'generate-coupons', self.admin_site.admin_view(GenerateCouponsAdminView.as_view()),
                name='generate_coupons'),

        ]
        return my_urls + urls

    gift_certificate_order.short_description = "Gift Certificate Order"
    gift_certificate_order.allow_tags = True


class GenerateCouponsAdminView(TemplateView):
    template_name = 'admin/generate_coupons.html'

    def get_context_data(self, **kwargs):
        context = super(GenerateCouponsAdminView, self).get_context_data(**kwargs)
        if self.request.method == 'POST':
            form = CouponGenerationForm(self.request.POST)
            if form.is_valid():
                context['coupons'] = Coupon.objects.create_coupons(
                    form.cleaned_data['quantity'],
                    form.cleaned_data['type'],
                    form.cleaned_data['value'],
                    form.cleaned_data['valid_until'],
                    form.cleaned_data['prefix'],
                    form.cleaned_data['campaign'],
                )
                messages.success(self.request, _("Your coupons have been generated."))
        else:
            form = CouponGenerationForm()
        context['form'] = form
        return context

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return self.render_to_response(context)


class CampaignAdmin(admin.ModelAdmin):
    list_display = ['name', 'num_coupons', 'num_coupons_used', 'num_coupons_unused', 'num_coupons_expired']

    def num_coupons(self, obj):
        return obj.coupons.count()
    num_coupons.short_description = _("coupons")

    def num_coupons_used(self, obj):
        return obj.coupons.used().count()
    num_coupons_used.short_description = _("used")

    def num_coupons_unused(self, obj):
        return obj.coupons.used().count()
    num_coupons_unused.short_description = _("unused")

    def num_coupons_expired(self, obj):
        return obj.coupons.expired().count()
    num_coupons_expired.short_description = _("expired")


admin.site.register(Coupon, CouponAdmin)
admin.site.register(Campaign, CampaignAdmin)
