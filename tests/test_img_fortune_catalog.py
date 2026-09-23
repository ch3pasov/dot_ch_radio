import json
import unittest

from libs.img_fortune_catalog import code_from_title, search_candidates, validate_catalog


class FortuneCatalogTests(unittest.TestCase):
    def test_titles_must_match_the_whole_filename(self):
        for title in (
            "IMG_6789", "img_6789", "IMG_6789.MOV", "img_6789.mov",
            "IMG_6789.MP4", "IMG_6789.M4V", "IMG_6789.AVI", "IMG_6789.3GP",
            "IMG_6789.MKV", "IMG_6789.WEBM", "IMG_6789.WMV", "IMG_6789.3G2",
        ):
            self.assertEqual(code_from_title(title), "6789")
        for title in ("IMG_6789.JPG", "IMG_67890", "IMG_6789 compilation", "IMG 6789"):
            self.assertIsNone(code_from_title(title))

    def test_search_discards_unrelated_recommendations(self):
        data = {"contents": [
            {"videoRenderer": {"videoId": "BFrPAsDt6w0", "title": {"runs": [{"text": "IMG_6789"}]}}},
            {"videoRenderer": {"videoId": "abcdefghijk", "title": {"runs": [{"text": "IMG_6789.MOV"}]}}},
        ]}
        results = search_candidates("<script>var ytInitialData = " + json.dumps(data) + ";</script>")
        self.assertEqual(results, [
            {"code": "6789", "video_id": "BFrPAsDt6w0", "title": "IMG_6789"},
            {"code": "6789", "video_id": "abcdefghijk", "title": "IMG_6789.MOV"},
        ])

    def test_consent_or_error_page_is_not_treated_as_empty_search(self):
        with self.assertRaises(ValueError):
            search_candidates("<html>Try again later</html>")

    def test_incomplete_or_mismatched_catalogues_cannot_be_deployed(self):
        catalog = {"schema_version": 1, "videos": {
            "6789": {"video_id": "BFrPAsDt6w0", "title": "IMG_6789", "verified_at": "2026-09-22T18:00:00+00:00"},
        }}
        with self.assertRaisesRegex(ValueError, "every code"):
            validate_catalog(catalog)
        self.assertEqual(len(validate_catalog(catalog, require_complete=False)), 1)
        catalog["videos"]["6789"]["title"] = "IMG_1234"
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_catalog(catalog, require_complete=False)
