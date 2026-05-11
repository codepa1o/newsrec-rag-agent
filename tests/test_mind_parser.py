from app.core.mind import parse_behavior_line, parse_news_line


def test_parse_news_line_handles_missing_optional_columns():
    article = parse_news_line("N1\ttech\tai\tTitle\tAbstract\n")

    assert article is not None
    assert article.news_id == "N1"
    assert article.category == "tech"
    assert article.title == "Title"
    assert article.abstract == "Abstract"


def test_parse_behavior_line_extracts_history_and_clicks():
    behavior = parse_behavior_line("1\tU1\t05/10/2026 08:00:00 AM\tN1 N2\tN3-1 N4-0\n")

    assert behavior is not None
    assert behavior.user_id == "U1"
    assert behavior.history == ("N1", "N2")
    assert behavior.impressions[0].news_id == "N3"
    assert behavior.impressions[0].clicked is True
