from rest_framework import viewsets, generics, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from .models import Book, Cart, CartItem, Order, OrderItem, Review
from .serializers import (
    BookSerializer,
    CartSerializer,
    CartItemSerializer,
    OrderSerializer,
    ReviewSerializer,
    UserSerializer,
    RegisterSerializer,
)
from .permissions import IsOwnerOrReadOnly


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["genre", "author"]
    search_fields = ["title", "author", "isbn", "description"]
    ordering_fields = ["title", "author", "price", "published_date"]

    def get_permissions(self):
        if self.action in ["create"]:
            permission_classes = [IsAuthenticated]
        elif self.action in ["update", "partial_update", "destroy"]:
            permission_classes = [IsOwnerOrReadOnly]
        else:
            permission_classes = [AllowAny]
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=["get"])
    def reviews(self, request, pk=None):
        book = self.get_object()
        reviews = book.reviews.all()
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Review.objects.filter(
            Q(book_id=self.kwargs.get("book_pk")) if "book_pk" in self.kwargs else Q()
        )

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy"]:
            return [IsAuthenticated()] 
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CartViewSet(viewsets.ModelViewSet):
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Cart.objects.filter(user=user)

    def list(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def add_item(self, request):
        serializer = CartItemSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Return updated cart
        cart = get_object_or_404(Cart, user=request.user)
        cart_serializer = CartSerializer(cart)
        return Response(cart_serializer.data)

    @action(detail=False, methods=["post"])
    def remove_item(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        book_id = request.data.get("book_id")

        try:
            cart_item = CartItem.objects.get(cart=cart, book_id=book_id)
            cart_item.delete()
            cart_serializer = CartSerializer(cart)
            return Response(cart_serializer.data)
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Book not found in cart"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["post"])
    def update_item(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        book_id = request.data.get("book_id")
        quantity = request.data.get("quantity", 1)

        try:
            cart_item = CartItem.objects.get(cart=cart, book_id=book_id)
            cart_item.quantity = quantity
            cart_item.save()
            cart_serializer = CartSerializer(cart)
            return Response(cart_serializer.data)
        except CartItem.DoesNotExist:
            return Response(
                {"error": "Book not found in cart"}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=False, methods=["post"])
    def clear(self, request):
        cart = get_object_or_404(Cart, user=request.user)
        cart.items.all().delete()
        cart_serializer = CartSerializer(cart)
        return Response(cart_serializer.data)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return Order.objects.filter(user=user)

    def perform_create(self, serializer):
        print(self.request.user)
        serializer.save(user=self.request.user)

    def get_permissions(self):
        if self.action in ["create"]:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsOwnerOrReadOnly]
        return [permission() for permission in permission_classes]
