from rest_framework import serializers
from django.contrib.auth.models import User, Group
from .models import MarketUser

class MarketUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=6,
        error_messages={
            "min_length": "Password must be exactly 6 characters long.",
            "max_length": "Password must be exactly 6 characters long."
        }
    )
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=True, max_length=20)

    class Meta:
        model = MarketUser
        fields = ['password', 'name', 'phone', 'email']

    def validate_email(self, value):
        """Check if the email already exists."""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_phone(self, value):
        """Ensure the phone number is unique."""
        if MarketUser.objects.filter(phone=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value

    def create(self, validated_data):
        email = validated_data.get('email')
        password = validated_data.get('password')

        # Create user in Django's built-in User model
        user = User.objects.create_user(
            username=email,  # Use email as username
            email=email,
            password=password
        )

        # Add user to "User" group
        user_group, _ = Group.objects.get_or_create(name="User")
        user.groups.add(user_group)

        # Create MarketUser profile
        market_user = MarketUser.objects.create(
            profile=user,
            name=validated_data.get('name'),
            phone=validated_data.get('phone'),
            email=email,
        )

        return market_user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketUser
        fields = ['id','name', 'phone', 'email','profile_picture','is_verified','is_banned']


class UpdateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketUser
        fields = ['name', 'phone', 'email', 'profile_picture']
        extra_kwargs = {
            'phone': {'required': False},
            'email': {'required': False},
            'name': {'required': False},
            'profile_picture': {'required': False},  # Make profile_picture optional
        }

    def update(self, instance, validated_data):

        instance.name = validated_data.get('name', instance.name)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.email = validated_data.get('email', instance.email)
        instance.profile_picture = validated_data.get('profile_picture', instance.profile_picture)

        if instance.registration_method == 'email':
            new_username = instance.email
        elif instance.registration_method == 'phone':
            new_username = instance.phone

        instance.profile.username = new_username
        instance.profile.save() 

        instance.save() 
        return instance