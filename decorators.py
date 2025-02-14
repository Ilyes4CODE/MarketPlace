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


def verified_user_required(view_func):
    """
    Decorator to ensure the user is verified before accessing the view.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return Response({"error": "يجب تسجيل الدخول للوصول إلى هذا المورد."}, status=status.HTTP_401_UNAUTHORIZED)

        if not hasattr(user, 'marketuser') or not user.marketuser.is_verified:
            return Response({"error": "يجب تأكيد حسابك أولاً."}, status=status.HTTP_403_FORBIDDEN)

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def not_banned_user_required(view_func):
    """
    Decorator to ensure the user is not banned before accessing the view.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user = request.user

        if not user.is_authenticated:
            return Response({"error": "يجب تسجيل الدخول للوصول إلى هذا المورد."}, status=status.HTTP_401_UNAUTHORIZED)

        if hasattr(user, 'marketuser') and user.marketuser.is_banned:
            return Response({"error": "تم حظر حسابك. لا يمكنك الوصول إلى هذا المورد."}, status=status.HTTP_403_FORBIDDEN)

        return view_func(request, *args, **kwargs)

    return _wrapped_view
