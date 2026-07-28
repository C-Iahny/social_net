from django import template
from django.db.models import Q
from django.utils import timezone
from personal.models import Announcement

register = template.Library()


@register.simple_tag
def get_active_announcements(count=5):
    """Retourne les annonces actives et dans leur période de diffusion."""
    now = timezone.now()
    return (
        Announcement.objects
        .filter(is_active=True, start_date__lte=now)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=now))
        .order_by('-start_date')[:count]
    )
