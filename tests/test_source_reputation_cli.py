from crypto_radar.cli import build_parser


def test_source_reputation_command_accepts_author_and_outcome():
    parser = build_parser()
    args = parser.parse_args(["source-reputation", "--author", "alice", "--record-outcome", "confirmed"])
    assert args.author == "alice"
    assert args.record_outcome == "confirmed"


def test_source_reputation_outcome_is_limited_to_explicit_values():
    parser = build_parser()
    try:
        parser.parse_args(["source-reputation", "--author", "alice", "--record-outcome", "guess"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("invalid outcome must fail")
