from rest_framework import serializers
from django.contrib.auth.models import User, Group
from .models import MarketUser

class MarketUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = MarketUser
        fields = ['password', 'name', 'phone', 'email']

    def validate(self, data):
        if not data.get('email') and not data.get('phone'):
            raise serializers.ValidationError("Either email or phone must be provided.")
        if data.get('email') and data.get('phone'):
            raise serializers.ValidationError("Provide either email or phone, not both.")
        return data

    def create(self, validated_data):
        if validated_data.get('email'):
            registration_method = 'email'
        elif validated_data.get('phone'):
            registration_method = 'phone'
        else:
            raise serializers.ValidationError("Either email or phone must be provided.")

        user = User.objects.create_user(
            username=validated_data.get('email') or validated_data.get('phone'),  # Use email or phone as username
            password=validated_data.get('password')
        )

        market_user = MarketUser.objects.create(
            profile=user,
            name=validated_data.get('name'),
            phone=validated_data.get('phone', ''),
            email=validated_data.get('email', ''),
            registration_method=registration_method
        )

        return market_user
    

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketUser
        fields = ['name', 'phone', 'email','profile_picture']


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