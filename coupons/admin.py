from django.db.models import Count, Q, F
from django.conf.urls import url
from django.contrib import admin
from django.contrib import messages
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.views.generic.base import TemplateView
from dateutil.relativedelta import relativedelta
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


class CouponAvailableListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _('Coupon Availability')

    # Parameter for the filter that will be used in the URL query.
    parameter_name = 'validity'

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return (
            ('Valid', _('Valid coupons')),
            ('UsedOrExpired', _('Redeemed or expired coupons')),
        )

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset based on the value
        provided in the query string and retrievable via
        `self.value()`.
        """
        # Compare the requested value
        # to decide how to filter the queryset.
        queryset = queryset.annotate(_coupon_usage=Count('users', filter=Q(users__redeemed_at__isnull=False)))
        select_filter = Q(
            Q(valid_until__gte=timezone.now()) | Q(valid_until__isnull=True)
        ) & Q(
            Q(user_limit=0) |
            Q(Q(user_limit__gt=0) & Q(_coupon_usage__lt=F('user_limit')))
        )

        if self.value() == 'Valid':
            return queryset.filter(select_filter)
        if self.value() == 'UsedOrExpired':
            return queryset.exclude(select_filter)


class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'description', 'coupon_value', 'usage', 'last_60_days_usage', 'valid_until', 'created_at',
    ]
    list_filter = (CouponAvailableListFilter, 'type', 'created_at', )
    raw_id_fields = ()
    search_fields = ('code', 'value', 'description')
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
        return mark_safe('<a href="%s">%s by %s on %s</a>' % (
            link,
            order.id,
            order.user.username,
            order.timestamp.date(),
        ))

    def usage(self, inst):
        if inst.user_limit != 0:
            return "{} of {}".format(inst._coupon_usage, inst.user_limit)
        else:
            return inst._coupon_usage

    def last_60_days_usage(self, inst):
        return inst._sixty_day_coupon_usage

    def coupon_value(self, inst):
        if inst.type == 'monetary':
            return '${}'.format(inst.value)
        elif inst.type == 'percentage':
            return '{:2.0f}%'.format(inst.value)
        else:
            return '{}'.format(inst.value)

    def get_urls(self):
        urls = super(CouponAdmin, self).get_urls()
        my_urls = [
            url(r'generate-coupons', self.admin_site.admin_view(GenerateCouponsAdminView.as_view()),
                name='generate_coupons'),

        ]
        return my_urls + urls

    def get_queryset(self, request):
        sixty_days_ago = timezone.now() - relativedelta(days=60)
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _coupon_usage=Count('users'),
            _sixty_day_coupon_usage=Count('users', filter=Q(users__redeemed_at__gte=sixty_days_ago))
        )
        return queryset

    gift_certificate_order.short_description = "Gift Certificate Order"
    usage.admin_order_field = '_coupon_usage'
    last_60_days_usage.admin_order_field = '_sixty_day_coupon_usage'
    last_60_days_usage.short_description = '60 day usage'


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
