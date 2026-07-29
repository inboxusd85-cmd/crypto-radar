import json
from pathlib import Path

from crypto_radar.cli import format_social_posts
from crypto_radar.social import SocialPost, SocialProviderError, XSearchAdapter, normalize_x_response


def test_normalize_x_response_extracts_post_and_author_metadata():
    response = {
        "data": [{"id": "123", "text": "HYPE funding is changing", "author_id": "42", "created_at": "2026-07-20T12:00:00.000Z", "public_metrics": {"like_count": 10, "reply_count": 2, "retweet_count": 3, "quote_count": 1}}],
        "includes": {"users": [{"id": "42", "username": "project", "name": "Project"}]},
    }
    posts = normalize_x_response(response, query="HYPE")
    assert posts == [SocialPost(platform="x", post_id="123", author_id="42", author_handle="project", text="HYPE funding is changing", created_at="2026-07-20T12:00:00.000Z", url="https://x.com/project/status/123", query="HYPE", engagement=16, source_quality=0.5)]


def test_normalize_x_response_deduplicates_post_ids():
    item = {"id": "123", "text": "same", "author_id": "42", "created_at": "2026-07-20T12:00:00Z"}
    assert len(normalize_x_response({"data": [item, item]}, query="HYPE")) == 1


def test_social_post_rejects_blank_identity():
    try:
        SocialPost(platform="x", post_id="", author_id="42", author_handle="a", text="x", created_at="now", url="u", query="q", engagement=0, source_quality=0.1)
    except ValueError as error:
        assert "post_id" in str(error)
    else:
        raise AssertionError("blank post_id must fail")


def test_format_social_posts_supports_json_and_markdown():
    post = SocialPost(platform="x", post_id="123", author_id="42", author_handle="project", text="HYPE funding is changing", created_at="2026-07-20T12:00:00Z", url="https://x.com/project/status/123", query="HYPE", engagement=16, source_quality=0.5)
    assert '"post_id": "123"' in format_social_posts([post], "json")
    assert "@project" in format_social_posts([post], "markdown")


def test_x_search_adapter_uses_read_only_json_command(tmp_path):
    executable = tmp_path / "xurl"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "print(json.dumps({'data': [{'id': '1', 'text': 'hello', 'author_id': '7', 'created_at': 'now'}]}))\n"
    )
    executable.chmod(0o755)
    posts = XSearchAdapter(str(executable)).search("HYPE", 3)
    assert posts[0].post_id == "1"


def test_x_search_adapter_reports_missing_executable():
    try:
        XSearchAdapter("definitely-missing-xurl").search("HYPE")
    except SocialProviderError as error:
        assert "not installed" in str(error)
    else:
        raise AssertionError("missing executable must fail")
