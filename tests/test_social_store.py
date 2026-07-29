from crypto_radar.social import SocialPost
from crypto_radar.social_store import SocialPostStore


def post(post_id="1", query="HYPE"):
    return SocialPost(
        platform="x", post_id=post_id, author_id="42", author_handle="project",
        text=f"post {post_id}", created_at="2026-07-20T12:00:00Z",
        url=f"https://x.com/project/status/{post_id}", query=query,
        engagement=10, source_quality=0.5,
    )


def test_store_upsert_is_idempotent_by_platform_and_post_id(tmp_path):
    store = SocialPostStore(tmp_path / "social.sqlite3")
    assert store.upsert(post("1")) is True
    assert store.upsert(post("1")) is False
    assert len(store.list_posts()) == 1


def test_store_lists_posts_with_query_filter_and_limit(tmp_path):
    store = SocialPostStore(tmp_path / "social.sqlite3")
    store.upsert(post("1", "HYPE"))
    store.upsert(post("2", "ZEC"))
    assert [item["post_id"] for item in store.list_posts(query="ZEC")] == ["2"]
    assert len(store.list_posts(limit=1)) == 1
