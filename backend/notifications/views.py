from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Every user sees only their own notifications.
        GET  /api/notifications/?is_read=false
        POST /api/notifications/{id}/read/
        POST /api/notifications/read-all/
        GET  /api/notifications/unread-count/
    """

    serializer_class = NotificationSerializer
    filterset_fields = ("is_read", "type")
    ordering = ("-created_at",)
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related("invoice")

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()  # someone else's id -> 404
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"marked_read": updated})

    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread": self.get_queryset().filter(is_read=False).count()})
