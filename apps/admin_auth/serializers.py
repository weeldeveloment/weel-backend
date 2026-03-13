from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate

User = get_user_model()


class AdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        if not email or not password:
            raise serializers.ValidationError('Email and password are required.')

        # Try to get the user by email (case-insensitive)
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            raise serializers.ValidationError('Invalid credentials.')

        # Check if user is staff/admin
        if not user.is_staff and not user.is_superuser:
            raise serializers.ValidationError('Access denied. Admin privileges required.')

        # Check if user is active
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled.')

        # Authenticate user with the model USERNAME_FIELD (usually `username`)
        username_field = getattr(User, 'USERNAME_FIELD', 'username')
        username_value = getattr(user, username_field, None)

        authenticated_user = None
        if username_value:
            authenticated_user = authenticate(**{username_field: username_value, 'password': password})

        # Fallback for custom auth setups: verify password directly
        if not authenticated_user and user.check_password(password):
            authenticated_user = user

        if not authenticated_user:
            raise serializers.ValidationError('Invalid credentials.')

        attrs['user'] = authenticated_user
        return attrs


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'is_staff', 'is_superuser']

    def get_full_name(self, obj):
        if hasattr(obj, 'first_name') and hasattr(obj, 'last_name'):
            return f"{obj.first_name} {obj.last_name}".strip() or obj.email
        if hasattr(obj, 'username'):
            return obj.username
        return obj.email


class AdminCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    is_staff = serializers.BooleanField(required=False, default=True)
    is_superuser = serializers.BooleanField(required=False, default=False)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('User with this email already exists.')
        return value

    def create(self, validated_data):
        email = validated_data['email']
        password = validated_data['password']
        first_name = validated_data.get('first_name', '')
        last_name = validated_data.get('last_name', '')
        is_staff = validated_data.get('is_staff', True)
        is_superuser = validated_data.get('is_superuser', False)

        base_username = email.split('@')[0]
        username = base_username
        suffix = 1
        while User.objects.filter(username=username).exists():
            suffix += 1
            username = f"{base_username}{suffix}"

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=True,
        )
        return user
