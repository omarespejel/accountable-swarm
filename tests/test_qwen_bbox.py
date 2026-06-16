from unittest import TestCase

from accountable_swarm.qwen.bbox import (
    parse_qwen_bbox_optional_response,
    parse_qwen_bbox_response,
    rescale_norm_1000_bbox,
)


class QwenBBoxTests(TestCase):
    def test_rescale_norm_1000_bbox(self) -> None:
        self.assertEqual(
            rescale_norm_1000_bbox((250, 250, 750, 750), image_width=640, image_height=480),
            (160, 120, 480, 360),
        )

    def test_rescale_tiny_norm_bbox_keeps_positive_pixel_area(self) -> None:
        self.assertEqual(
            rescale_norm_1000_bbox((1, 1, 2, 2), image_width=10, image_height=10),
            (0, 0, 1, 1),
        )

    def test_rescale_edge_tiny_norm_bbox_clamps_inside_image(self) -> None:
        self.assertEqual(
            rescale_norm_1000_bbox((999, 999, 1000, 1000), image_width=10, image_height=10),
            (9, 9, 10, 10),
        )

    def test_parse_prose_wrapped_json(self) -> None:
        parsed = parse_qwen_bbox_response(
            'Here: [{"bbox_2d":[0,100,1000,900],"label":"marked hazard"}]',
            image_width=100,
            image_height=50,
        )
        self.assertEqual(parsed.label, "marked hazard")
        self.assertEqual(parsed.bbox_2d_px, (0, 5, 100, 45))
        self.assertEqual(parsed.score_milli, 1000)

    def test_parse_quantizes_unit_score_to_milli(self) -> None:
        parsed = parse_qwen_bbox_response(
            '[{"bbox_2d":[0,100,1000,900],"label":"marked hazard","score":0.875}]',
            image_width=100,
            image_height=50,
        )

        self.assertEqual(parsed.score_milli, 875)

    def test_parse_accepts_direct_confidence_milli(self) -> None:
        parsed = parse_qwen_bbox_response(
            '[{"bbox_2d":[0,100,1000,900],"label":"marked hazard","confidence_milli":321}]',
            image_width=100,
            image_height=50,
        )

        self.assertEqual(parsed.score_milli, 321)

    def test_rejects_out_of_range_score(self) -> None:
        with self.assertRaises(ValueError):
            parse_qwen_bbox_response(
                '[{"bbox_2d":[0,0,1000,900],"label":"marked hazard","confidence":1.1}]',
                image_width=100,
                image_height=50,
            )

    def test_rejects_bool_score_milli(self) -> None:
        with self.assertRaises(ValueError):
            parse_qwen_bbox_response(
                '[{"bbox_2d":[0,0,1000,900],"label":"marked hazard","score_milli":true}]',
                image_width=100,
                image_height=50,
            )

    def test_rejects_missing_json(self) -> None:
        with self.assertRaises(ValueError):
            parse_qwen_bbox_response("no bbox here", image_width=100, image_height=50)

    def test_rejects_out_of_range_coordinates(self) -> None:
        with self.assertRaises(ValueError):
            parse_qwen_bbox_response(
                '[{"bbox_2d":[0,0,1001,900],"label":"marked hazard"}]',
                image_width=100,
                image_height=50,
            )

    def test_rejects_float_coordinates(self) -> None:
        with self.assertRaises(ValueError):
            parse_qwen_bbox_response(
                '[{"bbox_2d":[0.5,0,1000,900],"label":"marked hazard"}]',
                image_width=100,
                image_height=50,
            )

    def test_rejects_non_string_label(self) -> None:
        with self.assertRaises(ValueError):
            parse_qwen_bbox_response(
                '[{"bbox_2d":[0,0,1000,900],"label":false}]',
                image_width=100,
                image_height=50,
            )

    def test_rejects_empty_detection_array(self) -> None:
        with self.assertRaises(ValueError):
            parse_qwen_bbox_response("[]", image_width=100, image_height=50)

    def test_optional_response_accepts_empty_detection_array_with_whitespace(self) -> None:
        self.assertIsNone(parse_qwen_bbox_optional_response("[ ]", image_width=100, image_height=50))

    def test_optional_response_accepts_prose_wrapped_empty_detection_array(self) -> None:
        self.assertIsNone(parse_qwen_bbox_optional_response("no hazard: []", image_width=100, image_height=50))

    def test_optional_response_still_parses_non_empty_detection(self) -> None:
        parsed = parse_qwen_bbox_optional_response(
            '[{"bbox_2d":[0,100,1000,900],"label":"marked hazard"}]',
            image_width=100,
            image_height=50,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed.label, "marked hazard")
        self.assertEqual(parsed.bbox_2d_px, (0, 5, 100, 45))
