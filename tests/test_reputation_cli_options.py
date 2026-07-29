from crypto_radar.cli import build_parser


def test_cli_exposes_reputation_half_life():
    args = build_parser().parse_args(["social-analyze", "--aggregate", "--reputation-half-life", "48"])
    assert args.reputation_half_life == 48.0
