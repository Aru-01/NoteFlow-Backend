from django.urls import path
from .views import (
    GroupByInterestsView,
    PostDetailView,
    PostListCreateView,
    PostReactToggleView,
    UserPostsLookupView,
)

app_name = "posts"

urlpatterns = [
    path("", PostListCreateView.as_view(), name="post-list-create"),
    path("<int:pk>/", PostDetailView.as_view(), name="post-detail"),
    path("<int:pk>/react/", PostReactToggleView.as_view(), name="post-react-toggle"),
    path(
        "user/<int:user_id>/", UserPostsLookupView.as_view(), name="user-posts-lookup"
    ),
    path(
        "aggregations/group-by-interests/",
        GroupByInterestsView.as_view(),
        name="group-by-interests",
    ),
]
