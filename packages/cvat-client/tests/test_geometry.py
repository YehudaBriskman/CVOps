import pytest

from cvops_cvat_client.geometry import cvat_rect_to_norm_bbox, norm_bbox_to_cvat_rect


def test_norm_to_cvat_known_values():
    # Centered full-width-half-height box on a 200x100 image.
    # cx=0.5, cy=0.5, w=1.0, h=0.5 → x1=0, y1=25, x2=200, y2=75
    assert norm_bbox_to_cvat_rect([0.5, 0.5, 1.0, 0.5], 200, 100) == [0.0, 25.0, 200.0, 75.0]


def test_cvat_to_norm_known_values():
    cx, cy, w, h = cvat_rect_to_norm_bbox([0.0, 25.0, 200.0, 75.0], 200, 100)
    assert (cx, cy, w, h) == (0.5, 0.5, 1.0, 0.5)


@pytest.mark.parametrize(
    "coords,img_w,img_h",
    [
        ([0.5, 0.5, 0.2, 0.2], 640, 480),
        ([0.1, 0.9, 0.05, 0.15], 1920, 1080),
        ([0.5, 0.5, 1.0, 1.0], 100, 100),  # full-image box
        ([0.25, 0.75, 0.1, 0.3], 333, 777),
    ],
)
def test_round_trip_is_exact(coords, img_w, img_h):
    rect = norm_bbox_to_cvat_rect(coords, img_w, img_h)
    back = cvat_rect_to_norm_bbox(rect, img_w, img_h)
    assert back == pytest.approx(coords, abs=1e-9)


def test_corner_order_normalized():
    # A box given bottom-right→top-left must still yield positive w/h and the
    # same center as the canonical ordering.
    forward = cvat_rect_to_norm_bbox([0.0, 25.0, 200.0, 75.0], 200, 100)
    reversed_corners = cvat_rect_to_norm_bbox([200.0, 75.0, 0.0, 25.0], 200, 100)
    assert reversed_corners == forward
    assert reversed_corners[2] > 0 and reversed_corners[3] > 0


@pytest.mark.parametrize("bad", [[1, 2, 3], [1, 2, 3, 4, 5], []])
def test_rejects_wrong_length(bad):
    with pytest.raises(ValueError, match="4 coordinates"):
        norm_bbox_to_cvat_rect(bad, 100, 100)


@pytest.mark.parametrize("w,h", [(0, 100), (100, 0), (-1, 100), (100, -5)])
def test_rejects_nonpositive_dims(w, h):
    with pytest.raises(ValueError, match="dimensions must be positive"):
        norm_bbox_to_cvat_rect([0.5, 0.5, 0.2, 0.2], w, h)
