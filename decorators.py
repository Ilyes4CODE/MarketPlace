from functools import wraps
from rest_framework.response import Response
from rest_framework import status

def check_ban_status(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Assuming the request.user is authenticated
        if request.user.is_authenticated:
            profile = request.user.marketuser
            if profile.is_banned:
                return Response({"error": "You are banned from accessing this resource."}, status=status.HTTP_403_FORBIDDEN)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.groups.filter(name="Admin").exists():
            return Response({"error": "You are not authorized to perform this action."}, status=status.HTTP_403_FORBIDDEN)
        return view_func(request, *args, **kwargs)
    return _wrapped_view