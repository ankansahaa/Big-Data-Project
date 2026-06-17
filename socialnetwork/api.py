from django.db.models import Q, Exists, OuterRef, When, IntegerField, FloatField, Count, ExpressionWrapper, Case, Value, F, Prefetch

from fame.models import Fame, FameLevels, FameUsers, ExpertiseAreas
from socialnetwork.models import Posts, SocialNetworkUsers


# general methods independent of html and REST views
# should be used by REST and html views


def _get_social_network_user(user) -> SocialNetworkUsers:
    """Given a FameUser, gets the social network user from the request. Assumes that the user is authenticated."""
    try:
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise PermissionError("User does not exist")
    return user


def timeline(user: SocialNetworkUsers, start: int = 0, end: int = None, published=True, community_mode=False):
    """Get the timeline of the user. Assumes that the user is authenticated."""

    if community_mode:
        # T4
        # in community mode, posts of communities are displayed if ALL of the following criteria are met:
        # 1. the author of the post is a member of the community
        # 2. the user is a member of the community
        # 3. the post contains the community’s expertise area
        # 4. the post is published or the user is the author

        
        #########################
        community_query = Q()
        for community in user.communities.all():
            community_query |= Q(
                author__communities=community,
                expertise_area_and_truth_ratings=community
            )
        
        # If the user is a loner and isn't in any communities, return nothing
        if not community_query:
            posts = Posts.objects.none()
        else:
            # Apply our community filters AND the publication/author rules
            posts = Posts.objects.filter(community_query).filter(
                Q(published=published) | Q(author=user)
            ).distinct().order_by("-submitted")
        #########################

    else:
        # in standard mode, posts of followed users are displayed
        _follows = user.follows.all()
        posts = Posts.objects.filter(
            (Q(author__in=_follows) & Q(published=published)) | Q(author=user)
        ).order_by("-submitted")
    if end is None:
        return posts[start:]
    else:
        return posts[start:end+1]


def search(keyword: str, start: int = 0, end: int = None, published=True):
    """Search for all posts in the system containing the keyword. Assumes that all posts are public"""
    posts = Posts.objects.filter(
        Q(content__icontains=keyword)
        | Q(author__email__icontains=keyword)
        | Q(author__first_name__icontains=keyword)
        | Q(author__last_name__icontains=keyword),
        published=published,
    ).order_by("-submitted")
    if end is None:
        return posts[start:]
    else:
        return posts[start:end+1]


def follows(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """Get the users followed by this user. Assumes that the user is authenticated."""
    _follows = user.follows.all()
    if end is None:
        return _follows[start:]
    else:
        return _follows[start:end+1]


def followers(user: SocialNetworkUsers, start: int = 0, end: int = None):
    """Get the followers of this user. Assumes that the user is authenticated."""
    _followers = user.followed_by.all()
    if end is None:
        return _followers[start:]
    else:
        return _followers[start:end+1]


def follow(user: SocialNetworkUsers, user_to_follow: SocialNetworkUsers):
    """Follow a user. Assumes that the user is authenticated. If user already follows the user, signal that."""
    if user_to_follow in user.follows.all():
        return {"followed": False}
    user.follows.add(user_to_follow)
    user.save()
    return {"followed": True}


def unfollow(user: SocialNetworkUsers, user_to_unfollow: SocialNetworkUsers):
    """Unfollow a user. Assumes that the user is authenticated. If user does not follow the user anyway, signal that."""
    if user_to_unfollow not in user.follows.all():
        return {"unfollowed": False}
    user.follows.remove(user_to_unfollow)
    user.save()
    return {"unfollowed": True}


def submit_post(
    user: SocialNetworkUsers,
    content: str,
    cites: Posts = None,
    replies_to: Posts = None,
):
    """Submit a post for publication. Assumes that the user is authenticated.
    returns a tuple of three elements:
    1. a dictionary with the keys "published" and "id" (the id of the post)
    2. a list of dictionaries containing the expertise areas and their truth ratings
    3. a boolean indicating whether the user was banned and logged out and should be redirected to the login page
    """

    # create post  instance:
    post = Posts.objects.create(
        content=content,
        author=user,
        cites=cites,
        replies_to=replies_to,
    )

    # classify the content into expertise areas:
    # only publish the post if none of the expertise areas contains bullshit:
    _at_least_one_expertise_area_contains_bullshit, _expertise_areas = (
        post.determine_expertise_areas_and_truth_ratings()
    )
    post.published = not _at_least_one_expertise_area_contains_bullshit

    redirect_to_logout = False


    #########################
    # Loop through all the topics the Magic AI found in the post
    for ea_dict in _expertise_areas:
        ea = ea_dict.get("expertise_area")
        
        # Check the database: Does this user have negative fame for this topic?
        is_cancelled = Fame.objects.filter(
            user=user,
            expertise_area=ea,
            fame_level__numeric_value__lt=0
        ).exists()

        
        # If they are hated in this topic, kill the post and stop checking
        if is_cancelled:
            post.published = False
            break

    if _at_least_one_expertise_area_contains_bullshit:
        for ea_dict in _expertise_areas:
            truth_rating_obj = ea_dict.get("truth_rating")
            
            # FIXED: Safely check if the TruthRatings object's numeric value is negative
            if truth_rating_obj is not None and truth_rating_obj.numeric_value < 0:
                ea = ea_dict.get("expertise_area")
                
                try:
                    # Check if the user already has a Fame profile for this topic
                    fame_record = Fame.objects.get(user=user, expertise_area=ea)
                    
                    try:
                        # T2a: Attempt to downgrade them to the next lower fame tier
                        next_lower = fame_record.fame_level.get_next_lower_fame_level()
                        fame_record.fame_level = next_lower
                        fame_record.save()
                        # --- INSERT TASK 4d HERE ---
                        # If the new fame level is below 100 ("Super Pro"), kick them out!
                        if fame_record.fame_level.numeric_value < 100:
                            if user.communities.filter(id=ea.id).exists():
                                user.communities.remove(ea)
                                # Refresh user to ensure the cache is clear for the test assertion
                                user.refresh_from_db()
                        # ---------------------------
                    except ValueError:
                        # T2c: Cannot lower further -> Trigger the BAN HAMMER! 🔨
                        user.is_active = False
                        user.save()
                        
                        # Unpublish all of their existing posts efficiently in bulk
                        # Note: The assignment specifies setting published=False on their posts
                        Posts.objects.filter(author=user).update(published=False)
                        
                        # Mark redirection flags
                        redirect_to_logout = True
                        post.published = False  # Ensure current post is also unpublished
                        
                except Fame.DoesNotExist:
                    # T2b: No existing profile -> Create one with the "Confuser" level
                    try:
                        confuser_level = FameLevels.objects.get(name="Confuser")
                        Fame.objects.create(
                            user=user, 
                            expertise_area=ea, 
                            fame_level=confuser_level
                        )
                    except FameLevels.DoesNotExist:
                        pass
    #########################

    post.save()

    return (
        {"published": post.published, "id": post.id},
        _expertise_areas,
        redirect_to_logout,
    )


def rate_post(
    user: SocialNetworkUsers, post: Posts, rating_type: str, rating_score: int
):
    """Rate a post. Assumes that the user is authenticated. If user already rated the post with the given rating_type,
    update that rating score."""
    user_rating = None
    try:
        user_rating = user.userratings_set.get(post=post, rating_type=rating_type)
    except user.userratings_set.model.DoesNotExist:
        pass

    if user == post.author:
        raise PermissionError(
            "User is the author of the post. You cannot rate your own post."
        )

    if user_rating is not None:
        # update the existing rating:
        user_rating.rating_score = rating_score
        user_rating.save()
        return {"rated": True, "type": "update"}
    else:
        # create a new rating:
        user.userratings_set.add(
            post,
            through_defaults={"rating_type": rating_type, "rating_score": rating_score},
        )
        user.save()
        return {"rated": True, "type": "new"}


def fame(user: SocialNetworkUsers):
    """Get the fame of a user. Assumes that the user is authenticated."""
    try:
        user = SocialNetworkUsers.objects.get(id=user.id)
    except SocialNetworkUsers.DoesNotExist:
        raise ValueError("User does not exist")

    return user, Fame.objects.filter(user=user)


def bullshitters():
    """Return a Python dictionary mapping each existing expertise area in the fame profiles to a list of the users
    having negative fame for that expertise area. Each list should contain Python dictionaries as entries with keys
    ``user'' (for the user) and ``fame_level_numeric'' (for the corresponding fame value), and should be ranked, i.e.,
    users with the lowest fame are shown first, in case there is a tie, within that tie sort by date_joined
    (most recent first). Note that expertise areas with no expert may be omitted.
    """
    
    #########################
    negative_fame_records = Fame.objects.filter(
        fame_level__numeric_value__lt=0
    ).select_related('user', 'fame_level', 'expertise_area')

    result_dict = {}

    for record in negative_fame_records:
        ea_obj = record.expertise_area
        
        # FIXED: Just grab the user exactly as it is in the Fame record!
        # No extra database queries, no skipping users!
        user_obj = record.user

        user_entry = {
            "user": user_obj,
            "fame_level_numeric": record.fame_level.numeric_value
        }

        if ea_obj not in result_dict:
            result_dict[ea_obj] = []
        
        result_dict[ea_obj].append(user_entry)

    # Apply sorting rules
    for ea_obj in result_dict:
        result_dict[ea_obj].sort(
            key=lambda x: (
                x["fame_level_numeric"],           # Primary: Lowest fame value first (ascending)
                -x["user"].date_joined.timestamp() # Secondary Tie-Breaker: Most recent date first (descending)
            )
        )

    return result_dict
    ########################





def join_community(user: SocialNetworkUsers, community: ExpertiseAreas):
    """Join a specified community. Note that this method does not check whether the user is eligible for joining the
    community.
    """

    #########################
    if user.communities.filter(id=community.id).exists():
        return {"joined": False}
    
    user.communities.add(community)
    return {"joined": True}
    #########################



def leave_community(user: SocialNetworkUsers, community: ExpertiseAreas):
    """Leave a specified community."""
    
    #########################
    # 1. Reload the user from the database to get the latest state
    user.refresh_from_db()
    
    # 2. Check membership
    if not user.communities.filter(id=community.id).exists():
        return {"left": False}
    
    # 3. Remove the community
    user.communities.remove(community)
    
    return {"left": True}
    #########################



def similar_users(user: SocialNetworkUsers):
    """Compute the similarity of user with all other users. The method returns a QuerySet of FameUsers annotated
    with an additional field 'similarity'. Sort the result in descending order according to 'similarity', in case
    there is a tie, within that tie sort by date_joined (most recent first)"""

    # 1. Get user_i's expertise areas and fame values
    my_fame_records = user.fame_set.select_related('expertise_area', 'fame_level')
    if not my_fame_records.exists():
        return []

    my_fame_map = {f.expertise_area_id: f.fame_level.numeric_value for f in my_fame_records}
    my_expertise_ids = list(my_fame_map.keys())
    e_i_size = len(my_expertise_ids)

    # 2. Get all other users who share expertise
    candidates = SocialNetworkUsers.objects.filter(
        fame__expertise_area_id__in=my_expertise_ids
    ).exclude(id=user.id).distinct()

    similar_users_list = []

    # 3. Calculate score
    for candidate in candidates:
        score_sum = 0
        candidate_fame = {f.expertise_area_id: f.fame_level.numeric_value 
                          for f in candidate.fame_set.filter(expertise_area_id__in=my_expertise_ids)}
        
        for ea_id, my_fame in my_fame_map.items():
            if ea_id in candidate_fame:
                if abs(my_fame - candidate_fame[ea_id]) <= 100:
                    score_sum += 1
        
        similarity_score = score_sum / e_i_size
        
        if similarity_score > 0:
            # FIX: Attach the attribute directly to the object instance
            candidate.similarity = similarity_score
            similar_users_list.append(candidate)

    # 4. Sort: Descending by score, then by date_joined
    similar_users_list.sort(key=lambda x: (-x.similarity, -x.date_joined.timestamp()))

    return similar_users_list