from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import Book, Cart, CartItem, Order, Review
import json


class BookstoreAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create test users
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass",
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username="user", email="user@example.com", password="userpass"
        )

        # Create a cart for the regular user
        self.cart = Cart.objects.create(user=self.regular_user)

        # Create test books
        self.book1 = Book.objects.create(
            title="Test Book 1",
            author="Test Author 1",
            description="Test Description 1",
            price=19.99,
            isbn="1234567890123",
            genre="Fiction",
            published_date="2021-01-01",
            stock_quantity=10,
        )

        self.book2 = Book.objects.create(
            title="Test Book 2",
            author="Test Author 2",
            description="Test Description 2",
            price=29.99,
            isbn="9876543210987",
            genre="Non-Fiction",
            published_date="2022-01-01",
            stock_quantity=5,
        )

    def test_register_user(self):
        """Test user registration"""
        url = reverse("register")
        data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "newuserpass123",
            "password2": "newuserpass123",
            "first_name": "New",
            "last_name": "User",
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="newuser").exists())

        # Check if cart was created for the new user
        new_user = User.objects.get(username="newuser")
        self.assertTrue(Cart.objects.filter(user=new_user).exists())

    def test_login(self):
        """Test user authentication"""
        url = reverse("token_obtain_pair")
        data = {"username": "user", "password": "userpass"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_add_book(self):
        """Test adding a new book (admin only)"""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse("book-list")
        data = {
            "title": "New Book",
            "author": "New Author",
            "description": "New Description",
            "price": 15.99,
            "isbn": "1111222233334",
            "genre": "Mystery",
            "published_date": "2023-01-01",
            "stock_quantity": 20,
        }
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Book.objects.count(), 3)

    def test_get_book_details(self):
        """Test retrieving book details"""
        url = reverse("book-detail", args=[self.book1.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Test Book 1")
        self.assertEqual(response.data["author"], "Test Author 1")

    def test_search_books(self):
        """Test searching for books"""
        url = reverse("book-list")
        response = self.client.get(url, {"search": "Fiction"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["title"], "Test Book 1")

    def test_add_to_cart(self):
        """Test adding a book to cart"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("cart-add-item")
        data = {"book_id": self.book1.id, "quantity": 2}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["book"]["id"], self.book1.id)
        self.assertEqual(response.data["items"][0]["quantity"], 2)

    def test_place_order(self):
        """Test placing an order"""
        # First add items to cart
        self.client.force_authenticate(user=self.regular_user)
        CartItem.objects.create(cart=self.cart, book=self.book1, quantity=2)

        # Place order
        url = reverse("order-list")
        data = {"shipping_address": "123 Test St, Test City, TS 12345"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify order was created
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.first()
        self.assertEqual(order.user, self.regular_user)
        self.assertEqual(order.total_price, self.book1.price * 2)

        # Check if cart is empty after order
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 0)

        # Check if book stock was updated
        book1_updated = Book.objects.get(id=self.book1.id)
        self.assertEqual(book1_updated.stock_quantity, 8)  # 10 - 2

    def test_view_order_history(self):
        """Test viewing order history"""
        self.client.force_authenticate(user=self.regular_user)

        # Create an order for the user
        order = Order.objects.create(
            user=self.regular_user,
            shipping_address="123 Test St, Test City, TS 12345",
            total_price=self.book1.price * 2,
        )

        url = reverse("order-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], order.id)

    def test_write_review(self):
        """Test writing a review for a book"""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse("book-reviews", args=[self.book1.id])
        data = {"book": self.book1.id, "rating": 5, "text": "This is a great book!"}
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify review was created
        self.assertEqual(Review.objects.count(), 1)
        review = Review.objects.first()
        self.assertEqual(review.book, self.book1)
        self.assertEqual(review.user, self.regular_user)
        self.assertEqual(review.rating, 5)

    def test_security_check(self):
        """Test unauthorized access"""
        url = reverse("book-list")
        data = {
            "title": "Unauthorized Book",
            "author": "Unauthorized Author",
            "description": "Unauthorized Description",
            "price": 15.99,
            "isbn": "9999999999999",
            "genre": "Horror",
            "published_date": "2023-01-01",
            "stock_quantity": 20,
        }

        # Try to add book without authentication
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Try to add book with non-admin user
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
