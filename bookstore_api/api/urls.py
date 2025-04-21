from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, BookViewSet, ReviewViewSet, CartViewSet, OrderViewSet

router = DefaultRouter()
router.register(r"books", BookViewSet)
router.register(r"cart", CartViewSet, basename="cart")
router.register(r"orders", OrderViewSet, basename="order")
router.register(r"reviews", ReviewViewSet, basename="review")

urlpatterns = [
    path("", include(router.urls)),
    path("register/", RegisterView.as_view(), name="register"),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path(
        "books/<int:book_pk>/reviews/",
        ReviewViewSet.as_view({"get": "list", "post": "create"}),
        name="book-reviews",
    ),
]
