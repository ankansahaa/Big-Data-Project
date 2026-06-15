from django.urls import path

from socialnetwork.views.html import timeline
from socialnetwork.views.html import follow
from socialnetwork.views.html import unfollow
from socialnetwork.views.rest import PostsListApiView

app_name = "socialnetwork"

urlpatterns = [
    path("api/posts", PostsListApiView.as_view(), name="posts_fulllist"),
    path("html/timeline", timeline, name="timeline"),
    path("api/follow", follow, name="follow"),
    path("api/unfollow", unfollow, name="unfollow"),
]
