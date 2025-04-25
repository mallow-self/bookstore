from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import Book, Cart, CartItem, Order, OrderItem, Review


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = (
            "username",
            "password",
            "password2",
            "email",
            "first_name",
            "last_name",
        )

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
        )
        user.set_password(validated_data["password"])
        user.save()

        # Create a cart for the new user
        Cart.objects.create(user=user)

        return user


class BookSerializer(serializers.ModelSerializer):
    average_rating = serializers.SerializerMethodField()
    user = UserSerializer(read_only=True)

    class Meta:
        model = Book
        fields = (
            "id",
            "title",
            "author",
            "description",
            "price",
            "isbn",
            "genre",
            "user",
            "published_date",
            "stock_quantity",
            "cover_image",
            "average_rating",
            "created_at",
            "updated_at",
        )

    def get_average_rating(self, obj):
        reviews = obj.reviews.all()
        if not reviews:
            return None
        return sum(review.rating for review in reviews) / len(reviews)

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ("id", "book", "user", "rating", "text", "created_at", "updated_at")
        read_only_fields = ("user",)

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        book = attrs["book"]

        if Review.objects.filter(book=book, user=user).exists():
            raise serializers.ValidationError("You have already reviewed this book.")

        return attrs


class CartItemSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)
    book_id = serializers.PrimaryKeyRelatedField(
        queryset=Book.objects.all(), write_only=True
    )
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = CartItem
        fields = ("id", "book", "book_id", "quantity", "total_price")

    def create(self, validated_data):
        book = validated_data.pop("book_id")
        cart = Cart.objects.get(user=self.context["request"].user)

        # Check if the book is already in the cart
        try:
            cart_item = CartItem.objects.get(cart=cart, book=book)
            cart_item.quantity += validated_data.get("quantity", 1)
            cart_item.save()
            return cart_item
        except CartItem.DoesNotExist:
            return CartItem.objects.create(cart=cart, book=book, **validated_data)


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = Cart
        fields = ("id", "items", "total_price", "created_at", "updated_at")


class OrderItemSerializer(serializers.ModelSerializer):
    book = BookSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "book", "quantity", "price")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "user",
            "status",
            "shipping_address",
            "total_price",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("user", "total_price")

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data.pop("user", None)
        cart = Cart.objects.get(user=user)

        # Check if cart is empty
        if not cart.items.exists():
            raise serializers.ValidationError(
                {"error": "Cannot place order with empty cart"}
            )

        # Calculate total price from cart
        total_price = cart.total_price

        # Create order
        order = Order.objects.create(
            user=user, total_price=total_price, **validated_data
        )

        # Create order items from cart
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                book=cart_item.book,
                quantity=cart_item.quantity,
                price=cart_item.book.price,
            )

            # Update stock quantity
            book = cart_item.book
            book.stock_quantity -= cart_item.quantity
            book.save()

        # Empty the cart
        cart.items.all().delete()

        return order
