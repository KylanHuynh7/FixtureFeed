from fixturefeed.config import APP_NAME


def test_app_name_is_single_source_of_truth():
    assert APP_NAME == "FixtureFeed"
