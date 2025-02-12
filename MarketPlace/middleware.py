from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser, User
from django.conf import settings
import jwt
from asgiref.sync import sync_to_async

class JWTAuthMiddleware(BaseMiddleware):
    """Middleware to authenticate WebSocket connections using JWT tokens."""

    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope["query_string"].decode())
        token = query_string.get("token", [None])[0]  # Extract token from query params

        user = await self.get_user_from_token(token)

        scope["user"] = user  # ✅ Assign Django User model instance

        return await super().__call__(scope, receive, send)

    @sync_to_async
    def get_user_from_token(self, token):
        """Decodes the JWT token and retrieves the authenticated user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()  # ✅ Get the correct User model (custom or default)

        try:
            decoded_data = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = decoded_data.get("user_id")
            user = User.objects.get(id=user_id)

            return user  # ✅ Return Django User object

        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, User.DoesNotExist):
            return AnonymousUser()  # ✅ Anonymous users have `is_anonymous = True`
