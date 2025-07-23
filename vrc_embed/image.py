# SPDX-License-Identifier: MIT
"""Image generation code."""

from PIL import Image, ImageDraw


def generate_large(payload: dict) -> Image:
    """Generate a large (355x340) image."""

    # PIL/Pillow does not support antialiasing when drawing shapes; as such,
    # we have to fake it using supersampling. We draw the shapes on a canvas
    # 3x times the target resolution, then downscale it, then draw the text
    # (since text drawing is antialiased).

    sample = 2
    size = (355 * sample, 340 * sample)

    fg = payload.get("foreground_color", "#F8F9FA")

    img = Image.new("RGBA", size, "#00000000")
    draw = ImageDraw.Draw(img)

    draw.rounded_rectangle(
        ((0, 0), size),
        radius=payload.get("border_radius", 8 * sample),
        fill=payload.get("background_color", "#181B1F"),
    )

    # Last seen indicator

    ind_text_length = draw.textlength("56 minutes ago", font_size=8)
    ind_size = ((ind_text_length + 4 + 4) * sample, 8 + 4 + 4)
    ind_pos = (
        (((355) * sample) - ind_size[0], 8 * sample),
        (((355 - 8) * sample), (8 * sample) + ind_size[1]),
    )
    # Transparency is also broken, so we have to create a separate image and
    # blend it into the main one

    img2 = Image.new("RGBA", (), "#00000000")
    draw2 = ImageDraw.draw(img2)
    (draw2.rounded_rectangle,)
    draw.rounded_rectangle(
        (
            ((355 - ind_text_length - 8 - 4 - 4) * sample, 8 * sample),
            ((355 - 8) * sample, (8 + 4 + 8 + 4) * sample),
        ),
        radius=(8 + 4 + 8 + 4) * sample,
        fill="#111111cc",
    )

    size = (355, 340)
    img = img.resize(size, resample=Image.Resampling.BICUBIC)

    draw.text((355 - ind_text_length - 8 - 4, 8 + 4), "56 minutes ago", font_size=8)

    return img


if __name__ == "__main__":
    print("main")
    img = generate_large(
        {
            "username": "serialuart",
            "pronouns": "they/any",
            "state": "online",
            "status": ":3",
        }
    )
    img.show()
