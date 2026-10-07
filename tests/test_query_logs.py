from app.tools.logs import query_logs


def test_known_service_returns_all_lines_in_order():
    assert query_logs(service="checkout") == [
        "14:21 checkout-api ERROR database connection timeout",
        "14:22 checkout-api ERROR connection pool exhausted",
        "14:24 checkout-api WARN retrying database request",
    ]


def test_unknown_service_returns_empty_list():
    assert query_logs(service="inventory") == []


def test_keyword_filters_case_insensitively():
    assert query_logs(service="checkout", keyword="POOL") == [
        "14:22 checkout-api ERROR connection pool exhausted",
    ]


def test_keyword_without_match_returns_empty_list():
    assert query_logs(service="checkout", keyword="disk full") == []


def test_result_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert len(query_logs(service="checkout")) == 3
