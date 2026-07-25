"""Tests for community API diary/privacy behavior."""

from fastapi import status

from web.backend.database.models import (
    Bookmark,
    Collection,
    CollectionItem,
    CommunityCategory,
    Post,
    PostComment,
    User,
)
from web.backend.services.auth import create_access_token


def _auth_headers_for(username: str) -> dict[str, str]:
    token = create_access_token({"sub": username})
    return {"Authorization": f"Bearer {token}"}


def _seed_categories(db_session):
    diary = CommunityCategory(
        name="白白日记",
        description="记录每一天的心情与变化",
        icon="📓",
        order=0,
    )
    treatment = CommunityCategory(
        name="治疗分享",
        description="分享治疗经历、用药心得",
        icon="💊",
        order=1,
    )
    db_session.add_all([diary, treatment])
    db_session.commit()
    db_session.refresh(diary)
    db_session.refresh(treatment)
    return diary, treatment


def _create_user(db_session, username: str) -> User:
    from web.backend.services.auth import get_password_hash

    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("testpass123"),
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestCommunityDiaries:
    def test_create_diary_post_returns_privacy_fields(
        self, client, db_session, test_user
    ):
        diary, _ = _seed_categories(db_session)
        auth_headers = _auth_headers_for(test_user.username)

        response = client.post(
            "/api/community/posts",
            json={
                "title": "今天好一点",
                "content": "<p>记录一下今天的状态</p>",
                "category_id": diary.id,
                "is_private": True,
                "diary_date": "2026-04-18",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["is_private"] is True
        assert data["diary_date"] == "2026-04-18"

    def test_public_feed_hides_private_diary_posts(self, client, db_session, test_user):
        diary, treatment = _seed_categories(db_session)
        auth_headers = _auth_headers_for(test_user.username)

        private_response = client.post(
            "/api/community/posts",
            json={
                "title": "私密日记",
                "content": "<p>只给自己看</p>",
                "category_id": diary.id,
                "is_private": True,
                "diary_date": "2026-04-18",
            },
            headers=auth_headers,
        )
        assert private_response.status_code == status.HTTP_200_OK

        public_response = client.post(
            "/api/community/posts",
            json={
                "title": "公开治疗分享",
                "content": "<p>大家一起交流</p>",
                "category_id": treatment.id,
            },
            headers=auth_headers,
        )
        assert public_response.status_code == status.HTTP_200_OK

        response = client.get("/api/community/posts")

        assert response.status_code == status.HTTP_200_OK
        titles = [item["title"] for item in response.json()["items"]]
        assert "公开治疗分享" in titles
        assert "私密日记" not in titles

    def test_my_diaries_returns_current_users_private_diaries_only(
        self, client, db_session, test_user
    ):
        diary, _ = _seed_categories(db_session)
        auth_headers = _auth_headers_for(test_user.username)

        response = client.post(
            "/api/community/posts",
            json={
                "title": "我的日记",
                "content": "<p>今天继续记录</p>",
                "category_id": diary.id,
                "is_private": True,
                "diary_date": "2026-04-18",
            },
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK

        other_user_headers = _auth_headers_for("another-user")
        from web.backend.database.models import User
        from web.backend.services.auth import get_password_hash

        other_user = User(
            username="another-user",
            email="another@example.com",
            hashed_password=get_password_hash("testpass123"),
            is_active=True,
            is_admin=False,
        )
        db_session.add(other_user)
        db_session.commit()

        my_diaries_response = client.get(
            "/api/community/my-diaries", headers=auth_headers
        )
        assert my_diaries_response.status_code == status.HTTP_200_OK
        my_items = my_diaries_response.json()["items"]
        assert len(my_items) == 1
        assert my_items[0]["title"] == "我的日记"
        assert my_items[0]["is_private"] is True

        other_response = client.get(
            "/api/community/my-diaries", headers=other_user_headers
        )
        assert other_response.status_code == status.HTTP_200_OK
        assert other_response.json()["items"] == []


class TestCommunityCollections:
    def test_list_collection_items_requires_authentication(
        self, client, db_session, test_user
    ):
        _, treatment = _seed_categories(db_session)
        post = Post(
            user_id=test_user.id,
            title="公开帖子",
            content="<p>内容</p>",
            category_id=treatment.id,
            is_private=False,
        )
        db_session.add(post)
        db_session.commit()
        db_session.refresh(post)

        collection = Collection(
            user_id=test_user.id, name="我的收藏夹", is_public=False
        )
        db_session.add(collection)
        db_session.commit()
        db_session.refresh(collection)

        db_session.add(
            CollectionItem(collection_id=collection.id, post_id=post.id, sort_order=1)
        )
        db_session.commit()

        response = client.get(f"/api/community/collections/{collection.id}/items")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_collection_items_hides_private_collection_from_other_users(
        self, client, db_session, test_user
    ):
        _, treatment = _seed_categories(db_session)
        other_user = _create_user(db_session, "another-user")

        post = Post(
            user_id=test_user.id,
            title="公开帖子",
            content="<p>内容</p>",
            category_id=treatment.id,
            is_private=False,
        )
        db_session.add(post)
        db_session.commit()
        db_session.refresh(post)

        collection = Collection(
            user_id=test_user.id, name="私密收藏夹", is_public=False
        )
        db_session.add(collection)
        db_session.commit()
        db_session.refresh(collection)

        db_session.add(
            CollectionItem(collection_id=collection.id, post_id=post.id, sort_order=1)
        )
        db_session.commit()

        response = client.get(
            f"/api/community/collections/{collection.id}/items",
            headers=_auth_headers_for("another-user"),
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "收藏夹不存在"


class TestCommunityUserStats:
    def test_user_stats_returns_post_bookmark_and_comment_counts(
        self, client, db_session, test_user
    ):
        _, treatment = _seed_categories(db_session)
        other_user = _create_user(db_session, "community-peer")

        my_post = Post(
            user_id=test_user.id,
            title="我的帖子",
            content="<p>我发的内容</p>",
            category_id=treatment.id,
            is_private=False,
        )
        other_post = Post(
            user_id=other_user.id,
            title="别人的帖子",
            content="<p>他人内容</p>",
            category_id=treatment.id,
            is_private=False,
        )
        db_session.add_all([my_post, other_post])
        db_session.commit()
        db_session.refresh(my_post)
        db_session.refresh(other_post)

        db_session.add(Bookmark(user_id=test_user.id, post_id=other_post.id))
        db_session.add(
            PostComment(
                post_id=other_post.id,
                user_id=test_user.id,
                content="我来评论一下",
            )
        )
        db_session.commit()

        response = client.get(
            "/api/community/user-stats", headers=_auth_headers_for(test_user.username)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "post_count": 1,
            "bookmark_count": 1,
            "comment_count": 1,
        }


class TestDiaryType:
    """Tests for diary_type field and calendar endpoint."""

    def test_create_diary_with_type(self, client, db_session, test_user):
        diary, _ = _seed_categories(db_session)
        auth_headers = _auth_headers_for(test_user.username)

        response = client.post(
            "/api/community/posts",
            json={
                "title": "用药记录",
                "content": "<p>今天开始用他克莫司</p>",
                "category_id": diary.id,
                "is_private": True,
                "diary_date": "2026-07-20",
                "diary_type": "medication",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["diary_type"] == "medication"
        assert data["diary_date"] == "2026-07-20"

    def test_diary_calendar_endpoint(self, client, db_session, test_user):
        diary, _ = _seed_categories(db_session)
        auth_headers = _auth_headers_for(test_user.username)

        # Create diary entries for July 2026
        for day, dtype in [(15, "medication"), (16, "phototherapy"), (20, "mood")]:
            client.post(
                "/api/community/posts",
                json={
                    "title": f"日记 {day}",
                    "content": f"<p>内容 {day}</p>",
                    "category_id": diary.id,
                    "is_private": True,
                    "diary_date": f"2026-07-{day:02d}",
                    "diary_type": dtype,
                },
                headers=auth_headers,
            )

        # Get calendar for July 2026
        response = client.get(
            "/api/community/diary-calendar?year=2026&month=7",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["year"] == 2026
        assert data["month"] == 7
        assert "2026-07-15" in data["entries"]
        assert "2026-07-16" in data["entries"]
        assert "2026-07-20" in data["entries"]
        assert data["entries"]["2026-07-15"][0]["diary_type"] == "medication"

    def test_diary_calendar_empty_month(self, client, db_session, test_user):
        auth_headers = _auth_headers_for(test_user.username)

        response = client.get(
            "/api/community/diary-calendar?year=2025&month=1",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["entries"] == {}

    def test_diary_calendar_requires_auth(self, client, db_session):
        response = client.get("/api/community/diary-calendar?year=2026&month=7")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
