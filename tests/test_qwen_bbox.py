from unittest import TestCase

from accountable_swarm.qwen.bbox import parse_qwen_bbox_response, rescale_norm_1000_bbox


class QwenBBoxTests(TestCase):
    def test_rescale_norm_1000_bbox(self) -> None:
        self.assertEqual(
            rescale_norm_1000_bbox((250, 250, 750, 750), image_width=640, image_height=480),
            (160, 120, 480, 360),
        )

    def test_parse_prose_wrapped_json(self) -> None:
        parsed = parse_qwen_bbox_response(
            'Here: [{"bbox_2d":[0,100,1000,900],"label":"marked hazard"}]',
            image_width=100,
            image_height=50,
        )
        self.assertEqual(parsed.label, "marked hazard")
        self.assertEqual(parsed.bbox_2d_px, (0, 5, 100, 45))

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
