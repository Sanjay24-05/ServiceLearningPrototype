"""Low-level shape edits on an open python-pptx Presentation."""
from __future__ import annotations

from slideproof.units import Rect


def set_frame(prs, slide_id: int, shape_id: int, frame: Rect) -> None:
    """Set a shape's frame (EMU). Raises KeyError if the shape is not found."""
    slide = prs.slides.get(slide_id)
    if slide is None:
        raise KeyError(f"slide {slide_id}")
    for shape in slide.shapes:
        if shape.shape_id == shape_id:
            shape.left, shape.top = int(frame.x), int(frame.y)
            shape.width, shape.height = int(frame.w), int(frame.h)
            return
    raise KeyError(f"s{slide_id}-sh{shape_id}")


def delete_shape(prs, slide_id: int, shape_id: int) -> None:
    """Remove a shape from a slide. Raises KeyError if the shape is not found."""
    slide = prs.slides.get(slide_id)
    if slide is None:
        raise KeyError(f"slide {slide_id}")
    for shape in slide.shapes:
        if shape.shape_id == shape_id:
            el = shape._element
            el.getparent().remove(el)
            return
    raise KeyError(f"s{slide_id}-sh{shape_id}")
