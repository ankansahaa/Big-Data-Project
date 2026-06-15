from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from socialnetwork import api
from socialnetwork.api import _get_social_network_user
from socialnetwork.models import SocialNetworkUsers
from socialnetwork.serializers import PostsSerializer


@require_http_methods(["GET"])
@login_required
def timeline(request):
    # using the serializer to get the data, then use JSON in the template!
    # avoids having to do the same thing twice

    # initialize community mode to False the first time in the session
    if 'community_mode' not in request.session:
        request.session['community_mode'] = False


    # get extra URL parameters:
    keyword = request.GET.get("search", "")
    published = request.GET.get("published", True)
    error = request.GET.get("error", None)

    # if keyword is not empty, use search method of API:
    if keyword and keyword != "":
        context = {
            "posts": PostsSerializer(
                api.search(keyword, published=published), many=True
            ).data,
            "searchkeyword": keyword,
            "error": error,
            "followers": list(api.follows(_get_social_network_user(request.user)).values_list('id', flat=True)),
        }
    else:  # otherwise, use timeline method of API:

        context = {
            "posts": PostsSerializer(
                api.timeline(
                    _get_social_network_user(request.user),
                    published=published,
                ),
                many=True,
            ).data,
            "searchkeyword": "",
            "error": error,
            "followers": list(api.follows(_get_social_network_user(request.user)).values_list('id', flat=True)),
        }

    return render(request, "timeline.html", context=context)


@require_http_methods(["POST"])
@login_required
def follow(request):
    user = _get_social_network_user(request.user)
    user_to_follow = SocialNetworkUsers.objects.get(id=request.POST.get("user_id"))
    api.follow(user, user_to_follow)
    return redirect(reverse("sn:timeline"))


@require_http_methods(["POST"])
@login_required
def unfollow(request):
    user = _get_social_network_user(request.user)
    user_to_unfollow = SocialNetworkUsers.objects.get(id=request.POST.get("user_id"))
    api.unfollow(user, user_to_unfollow)
    return redirect(reverse("sn:timeline"))


@require_http_methods(["GET"])
@login_required
def bullshitters(request):
    raise NotImplementedError("Not implemented yet")

@require_http_methods(["POST"])
@login_required
def toggle_community_mode(request):
    raise NotImplementedError("Not implemented yet")

@require_http_methods(["POST"])
@login_required
def join_community(request):
    raise NotImplementedError("Not implemented yet")

@require_http_methods(["POST"])
@login_required
def leave_community(request):
    raise NotImplementedError("Not implemented yet")

@require_http_methods(["GET"])
@login_required
def similar_users(request):
    raise NotImplementedError("Not implemented yet")
