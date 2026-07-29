from crypto_radar.cli import build_parser


def test_social_cli_exposes_freshness_half_life():
    parser = build_parser()
    args = parser.parse_args(["social-analyze", "--aggregate", "--freshness-half-life", "12"])
    assert args.freshness_half_life == 12.0


def test_social_cli_rejects_non_positive_freshness_half_life():
    parser = build_parser()
    try:
        parser.parse_args(["social-analyze", "--freshness-half-life", "0"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("non-positive half-life must fail")
