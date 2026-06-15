from django.test import TestCase
from django.db.models import F
import random as rnd

from socialnetwork import api

# make tests deterministic:
rnd.seed(42)

from fame.models import Fame, ExpertiseAreas, FameLevels
from famesocialnetwork.library import test_paths_for_allowed_and_forbidden_users
from socialnetwork.models import (
    Posts,
    SocialNetworkUsers,
    TruthRatings,
    UserRatings,
    PostExpertiseAreasAndRatings,
)


class ViewExistsTests(TestCase):
    fixtures = ["database_dump.json"]

    def test_view_overview_exists_fm(self):
        test_paths_for_allowed_and_forbidden_users(
            self,
            paths=[
                "/",
            ],
            users_allowed="N",
            users_forbidden="",
        )


class DataConsistencyTests(TestCase):
    """Tests for the data consistency of the database in the sense whether certain constraints are met."""

    fixtures = ["database_dump.json"]

    def test_basic_fake_data(self):
        user_count = SocialNetworkUsers.objects.count()
        self.assertTrue(user_count >= 20)
        self.assertTrue(Fame.objects.count() >= user_count * 2)
        self.assertTrue(ExpertiseAreas.objects.count() >= 10)
        self.assertTrue(FameLevels.objects.count() >= 10)
        self.assertTrue(TruthRatings.objects.count() >= 8)
        self.assertTrue(UserRatings.objects.count() >= 3 * Posts.objects.count())
        self.assertTrue(
            PostExpertiseAreasAndRatings.objects.count() >= 2 * Posts.objects.count()
        )
        # no banned users in fake data to start with:
        self.assertFalse(SocialNetworkUsers.objects.filter(is_banned=True).exists())

    def test_posts_created(self):
        self.assertTrue(Posts.objects.count() >= 400)
        self.assertTrue(Posts.objects.filter(published=True).exists())
        self.assertTrue(Posts.objects.filter(published=False).exists())
        self.assertFalse(Posts.objects.filter(content=False).exists())
        self.assertFalse(Posts.objects.filter(content="").exists())

    def test_posts_rated(self):
        self.assertTrue(
            PostExpertiseAreasAndRatings.objects.filter(
                truth_rating__isnull=False
            ).exists()
        )
        self.assertTrue(
            PostExpertiseAreasAndRatings.objects.filter(
                truth_rating__isnull=True
            ).exists()
        )

        post_count = Posts.objects.count()

        self.assertTrue(PostExpertiseAreasAndRatings.objects.count() >= post_count * 2)
        self.assertTrue(UserRatings.objects.count() >= post_count * 3)

    def test_post_no_negatively_rated_posts_are_published(self):
        # no post with a negative truth rating should be published:
        self.assertFalse(
            PostExpertiseAreasAndRatings.objects.filter(
                post__published=True, truth_rating__numeric_value__lt=0
            ).exists()
        )


class StudentTasksTests(TestCase):
    fixtures = ["database_dump.json"]

    def test_post_no_negatively_rated_posts_are_published_individual(self):
        # no post with a negative truth rating should be published:

        # pick a random post with a negative truth rating:
        negative_post_rating = rnd.choice(
            PostExpertiseAreasAndRatings.objects.filter(
                truth_rating__numeric_value__lt=0,
            )
        )
        # get the content of the post:
        content = negative_post_rating.post.content

        # get a random user different from the original author:
        user = rnd.choice(
            SocialNetworkUsers.objects.filter(
                fame__fame_level__numeric_value__lt=0,
                fame__fame_level__numeric_value__gte=-100,
            ).exclude(id=negative_post_rating.post.author.id)
        )

        ret_dict, _expertise_areas, redirect_to_logout = api.submit_post(
            user, content, cites=None, replies_to=None
        )
        self.assertFalse(ret_dict["published"])
        self.assertEqual(len(_expertise_areas), 2)

    def test_T1(
        self,
    ):  # implemented and tested
        # Task 1
        # change api.submit_post to not publish posts that have an expertise area which is contained in the user’s
        # fame profile and marked negative there (independent of any truth rating determined by the magic AI for
        # this post)

        # pick a random post without truth rating:
        negative_post_rating = rnd.choice(
            PostExpertiseAreasAndRatings.objects.filter(
                truth_rating=None,
            )
        )
        # get the expertise area and content of this post:
        expertise_area = negative_post_rating.expertise_area
        # get the content of the post:
        content = negative_post_rating.post.content

        # get a random user different from the original author who has a negative fame level for this expertise area
        user = rnd.choice(
            SocialNetworkUsers.objects.filter(
                fame__expertise_area=expertise_area,
                fame__fame_level__numeric_value__lt=0,
            ).exclude(id=negative_post_rating.post.author.id)
        )

        # for this user: send a new post with the exact same content:
        # recall, that eas and truth ratings are guaranteed to be the same for the same content
        ret_dict, _expertise_areas, redirect_to_logout = api.submit_post(
            user, content, cites=None, replies_to=None
        )

        self.assertFalse(ret_dict["published"])
        self.assertEqual(len(_expertise_areas), 2)

    # Task 2
    # change api.submit_post to adjust the fame profile of the user if he/she submits a post with a negative
    # truth rating
    def test_T2a(self):  # implemented and tested
        # If the expertise area is already contained in the user’s fame profile, lower the fame to the next
        # possible level.

        # pick a random post with a negative truth rating:
        negative_post_rating = rnd.choice(
            PostExpertiseAreasAndRatings.objects.filter(
                truth_rating__numeric_value__lt=0,
            )
        )
        # get the expertise area and content of this post:
        expertise_area = negative_post_rating.expertise_area
        # get the content of the post:
        content = negative_post_rating.post.content

        # get a random user different from the original author who has a negative fame level for this expertise area
        # (which is not on the lowest fame level):
        user = rnd.choice(
            SocialNetworkUsers.objects.filter(
                fame__expertise_area=expertise_area,
                fame__fame_level__numeric_value__lt=0,
                fame__fame_level__numeric_value__gte=-100,
            ).exclude(id=negative_post_rating.post.author.id)
        )

        # for this user get the old fame for this expertise area:
        old_fame_level = Fame.objects.get(
            user=user, expertise_area=expertise_area
        ).fame_level

        # for this user: send a new post with the exact same content:
        # recall, that eas and truth ratings are guaranteed to be the same for the same content
        api.submit_post(user, content, cites=None, replies_to=None)

        # for this user: get the new fame for this expertise area:
        new_fame_level = Fame.objects.get(
            user=user, expertise_area=expertise_area
        ).fame_level

        # the new fame level for this user must be different now:
        self.assertFalse(old_fame_level == new_fame_level)

        # the new fame level for this user must actually be the next lower fame level:
        self.assertTrue(old_fame_level.get_next_lower_fame_level() == new_fame_level)

    def test_T2b(self):  # implemented and tested
        # If the expertise area is not contained, simply add an entry in the user’s fame profile with fame
        # level “Confuser”.

        # pick a random post with a negative truth rating:
        negative_post_rating = rnd.choice(
            PostExpertiseAreasAndRatings.objects.filter(
                truth_rating__numeric_value__lt=0,
            )
        )
        # get the expertise area and content of this post:
        expertise_area = negative_post_rating.expertise_area
        # get the content of the post:
        content = negative_post_rating.post.content

        # get a random user different from the original author who DOES NOT HAVE this expertise area in his/her fame
        # profile:
        all_user_ids_without_expertise_area = list(
            set(SocialNetworkUsers.objects.all().values_list("id", flat=True))
            - set(
                Fame.objects.filter(expertise_area=expertise_area).values_list(
                    "user", flat=True
                )
            )
        )

        # pick a random user from the remaining users:
        user = SocialNetworkUsers.objects.get(
            id=rnd.choice(all_user_ids_without_expertise_area)
        )

        # for this user no fame entry with this ea should exist:
        self.assertFalse(
            Fame.objects.filter(user=user, expertise_area=expertise_area).exists()
        )

        # for this user: send a new post with the exact same content:
        # recall, that eas and truth ratings are guaranteed to be the same for the same content
        api.submit_post(user, content, cites=None, replies_to=None)

        # for this user: get the newly created fame entry for this expertise area:
        new_fame_level = Fame.objects.get(
            user=user, expertise_area=expertise_area
        ).fame_level

        # the fame_level should be "Confuser":
        self.assertEqual(new_fame_level.name, "Confuser")

    def _user_is_banned_test(self, use_DRF_endpoint: bool = False):
        # If you cannot lower the existing fame level for that expertise area any further, ban the user from the
        # social network by
        # setting the field is_banned,

        # pick a random post with a negative truth rating:
        negative_post_rating = rnd.choice(
            PostExpertiseAreasAndRatings.objects.filter(
                truth_rating__numeric_value__lt=0,
            )
        )
        # get the expertise area and content of this post:
        expertise_area = negative_post_rating.expertise_area
        # get the content of the post:
        content = negative_post_rating.post.content

        # get a random user different from the original author who has a "Dangerous Bullshitter" fame level for this
        # expertise area
        user = rnd.choice(
            SocialNetworkUsers.objects.filter(
                fame__expertise_area=expertise_area,
            ).exclude(id=negative_post_rating.post.author.id)
        )
        # manipulate fame level entry for this user:
        old_fame_entry = Fame.objects.get(user=user, expertise_area=expertise_area)
        old_fame_level = old_fame_entry.fame_level
        old_fame_entry.fame_level = FameLevels.objects.get(name="Dangerous Bullshitter")
        old_fame_entry.save()

        # for this user: send a new post with the exact same content:
        # recall, that eas and truth ratings are guaranteed to be the same for the same content
        if use_DRF_endpoint:
            self.client.login(email=user.email, password="test")
            ret = self.client.post(
                "/sn/api/posts",
                {"text": content},
            )
            self.assertEqual(ret.status_code, 302)
            self.assertFalse(ret.url.endswith("timeline"))

        else:
            ret, _expertise_areas, redirect_to_logout = api.submit_post(
                user, content, cites=None, replies_to=None
            )
            self.assertTrue(redirect_to_logout)

        # for this user: get the new fame for this expertise area:
        new_fame_level = Fame.objects.get(
            user=user, expertise_area=expertise_area
        ).fame_level

        # same fame level as before:
        self.assertTrue(new_fame_level.name == "Dangerous Bullshitter")

        user_reread = SocialNetworkUsers.objects.get(id=user.id)
        self.assertFalse(user_reread.is_active)

        # restore old fame level:
        old_fame_entry.fame_level = old_fame_level
        old_fame_entry.save()

        return user

    def test_T2c_1(self):  # implemented and tested
        self._user_is_banned_test()

    def test_T2c_2(self):  # implemented and tested
        # logging out the user if he/she sends another GET request,
        # call the endpoint to check whether it logs out the user
        self._user_is_banned_test(use_DRF_endpoint=True)

    def test_T2c_3(self):  # implemented and tested
        # disallowing him/her to ever login again.
        user = self._user_is_banned_test()
        login = self.client.login(email=user.email, password="test")
        self.assertFalse(login)

    def test_T2c_4(self):  # implemented and tested
        # unpublish all her/his posts (without deleting them from the database)
        user = self._user_is_banned_test()

        # get all posts for this user:
        user_posts = Posts.objects.filter(author=user)
        for post in user_posts:
            # check whether the post is unpublished:
            self.assertFalse(post.published)

    def _test_containment(self, my_dictionary, filter_conditions, reverse=False):
        # test whether everything returned is actually contained in the database:
        test_set = set()
        for ea, value in my_dictionary.items():
            # print(ea)
            previous_fame_level_numeric = None
            previous_date_joined = None
            for v in value:
                user = v["user"]
                fame_level_numeric = v["fame_level_numeric"]
                # date_joined = user.date_joined
                # print("\t", user, ea, fame_level_numeric, date_joined)
                self.assertTrue(
                    Fame.objects.filter(
                        user=user,
                        expertise_area=ea,
                        fame_level__numeric_value=fame_level_numeric,
                    ).exists()
                )
                # sort by numeric_value (or reversed), test this:
                self.assertTrue(
                    previous_fame_level_numeric is None  # first iteration or new ea
                    or (
                        reverse
                        and (
                            previous_fame_level_numeric >= fame_level_numeric
                        )  # sort on numeric_value descending
                    )
                    or (
                        not reverse
                        and (
                            previous_fame_level_numeric <= fame_level_numeric
                        )  # sort on numeric_value ascending
                    )
                )
                # within that tie sort by date_joined (most recent first), test this:
                self.assertTrue(
                    previous_date_joined is None  # first iteration or new ea
                    or previous_fame_level_numeric != fame_level_numeric  # new fame level
                    or previous_date_joined >= user.date_joined  # tie: sort on date_joined descending
                )

                previous_date_joined = user.date_joined
                previous_fame_level_numeric = fame_level_numeric

                # add to test set for vice versa test:
                test_set.add((user, ea, fame_level_numeric))

        # vice versa: test whether everything in the database is contained in the result:
        for fame_entry in Fame.objects.filter(**filter_conditions):
            user = fame_entry.user
            ea = fame_entry.expertise_area
            fame_level_numeric = fame_entry.fame_level.numeric_value
            self.assertTrue((user, ea, fame_level_numeric) in test_set)

    def test_T3(self):  # implemented and tested
        # implement api.bullshitters: It should return for each existing expertise area in the fame profiles a list
        # of the users having negative fame for that expertise area, the list should be ranked, i.e. users with the
        # lowest fame are shown first, in case there is a tie, within that tie sort by date_joined (most recent first)

        filter_conditions = {"fame_level__numeric_value__lt": 0}
        self._test_containment(api.bullshitters(), filter_conditions, reverse=False)

    def test_T4a(self):
        # Implement api.join_community, which adds a given user to a given community.

        # pick a random community
        community = rnd.choice(list(ExpertiseAreas.objects.all()))

        # get a random user whose fame_level in this expertise area is at least Super Pro
        all_user_ids_that_can_join_community = list(
            Fame.objects.filter(
                expertise_area=community,
                fame_level__numeric_value__gte=100
            ).values_list(
                "user", flat=True
            )
        )
        user = SocialNetworkUsers.objects.get(
            id=rnd.choice(all_user_ids_that_can_join_community)
        )

        # join the community
        api.join_community(user, community)

        # verify that the user has joined the community
        self.assertTrue(community in user.communities.all())

    def test_T4b(self):
        # Implement api.leave_community, which removes a given user from a given community.

        # pick a random user that is member of at least one community
        user = rnd.choice(list(SocialNetworkUsers.objects.filter(communities__isnull=False).distinct()))

        # pick a random community of this user
        community_to_leave = rnd.choice(list(user.communities.all()))

        # leave the community
        api.leave_community(user, community_to_leave)

        # assert that the user is no longer member of the community
        self.assertTrue(community_to_leave not in user.communities.all())

    def _should_be_displayed_in_community_mode(self, user, post):
        user_communities = list(user.communities.all())
        post_expertise_areas = list(post.expertise_area_and_truth_ratings.all())
        exists_valid_community = False
        author = post.author
        author_communities = list(author.communities.all())

        # verify that the post has at least one expertise area of which both user and author are member
        for expertise_area in post_expertise_areas:
            if expertise_area in user_communities and expertise_area in author_communities:
                exists_valid_community = True

        # verify that post is either published or the author is the user himself
        return exists_valid_community and (post.published or author == user)

    def test_T4c_1(self):
        # Change api.timeline to return all posts to be displayed when in community mode.
        # Scenario: user is member of at least one community

        # pick a random user that is member of at least one community
        user = rnd.choice(list(SocialNetworkUsers.objects.filter(communities__isnull=False).distinct()))

        # get displayed posts for this user
        displayed_posts = api.timeline(user, community_mode=True)

        # verify that all posts which are displayed fulfill the criteria
        user_communities = list(user.communities.all())
        for post in displayed_posts:
            self.assertTrue(self._should_be_displayed_in_community_mode(user, post))

        # verify that all posts which are not displayed do not fulfill the criteria
        non_displayed_posts = Posts.objects.exclude(id__in=displayed_posts.values('id'))
        for post in non_displayed_posts:
            self.assertFalse(self._should_be_displayed_in_community_mode(user, post))

    def test_T4c_2(self):
        # Change api.timeline to return all posts to be displayed when in community mode.
        # Scenario: user is not member of any one community

        # pick a random user that is not member of any community
        user = rnd.choice(list(SocialNetworkUsers.objects.filter(communities__isnull=True).distinct()))

        # get displayed posts for this user
        displayed_posts = api.timeline(user, community_mode=True)

        # verify that no posts are displayed for this user
        self.assertFalse(displayed_posts.exists())

    def test_T4d(self):
        # Change api.submit_post to automatically remove a user from a community if the fame level for the
        # expertise area of this community drops below Super Pro.

        # pick a random user who is in a community and has fame level Super Pro in this expertise area
        user_community_matches = Fame.objects.filter(
            fame_level__numeric_value=100,
            user__socialnetworkusers__communities=F('expertise_area')
            # ensures the user is a community member of the expertise area
        ).select_related('user', 'expertise_area')
        user, community = rnd.choice([(f.user, f.expertise_area) for f in user_community_matches])
        user = SocialNetworkUsers.objects.get(id=user.id)

        # pick a random post with negative truth rating in this expertise area and get its content
        negative_rated_posts = Posts.objects.filter(
            postexpertiseareasandratings__expertise_area=community,
            postexpertiseareasandratings__truth_rating__numeric_value__lt=0
        ).distinct()
        content = rnd.choice(list(negative_rated_posts)).content

        # for this user: send a new post with the exact same content
        api.submit_post(user, content, cites=None, replies_to=None)

        # assert that the user is no longer member of the community
        self.assertTrue(community not in user.communities.all())

    def test_T5_1(self):
        # Implement api.similar_users: It should return for a given user u_i the list of similar users. This list should
        # only contain other users with a non-zero similarity score and should be in descending order
        # according to their similarity score.
        # This test only checks basic properties of the result format and does not verify that the result is
        # entirely correct.

        # pick a random user
        user = rnd.choice(list(SocialNetworkUsers.objects.all()))

        # compute the similarities to all other users
        similar_users = api.similar_users(user)

        # verify that the result contains the field 'similarity'
        for similar_user in similar_users:
            self.assertTrue(hasattr(similar_user, 'similarity'))

        # verify that the similarities are sorted in descending order
        similarities = [user.similarity for user in similar_users]
        self.assertTrue(similarities == sorted(similarities, reverse=True))

        # verify that all similarities are between 0.0 (excluding) and 1.0 (including)
        self.assertTrue(all(0.0 < u.similarity <= 1.0 for u in similar_users))

    def test_T5_2(self):
        # Implement api.similar_users: It should return for a given user u_i the list of similar users. This list should
        # only contain other users with a non-zero similarity score and should be in descending order
        # according to their similarity score.
        # This test verifies the correctness of the result for a specific user.

        # pick a specific user
        user = SocialNetworkUsers.objects.get(id=21)

        # compute the similarities to all other users
        similar_users = api.similar_users(user)

        # verify that the user ids and similarity values are correct
        user_ids = [user.id for user in similar_users]
        similarities = [user.similarity for user in similar_users]
        true_user_ids = [19, 16, 20, 15, 10, 1, 13, 12, 11, 7, 4, 3, 17, 14, 9, 8, 5, 18, 6, 2]
        true_similarities = [0.6875, 0.6875, 0.625, 0.625, 0.5625, 0.5625, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.4375,
                             0.4375, 0.4375, 0.4375, 0.4375, 0.375, 0.375, 0.3125]
        self.assertTrue(user_ids == true_user_ids)
        self.assertTrue(similarities == true_similarities)
