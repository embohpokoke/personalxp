from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "frontend" / "icons"


def draw_icon(size: int) -> None:
    image = Image.new("RGBA", (size, size), "#f4fbf5")
    draw = ImageDraw.Draw(image)
    pad = size // 7
    radius = size // 5
    draw.rounded_rectangle((pad, pad, size - pad, size - pad), radius=radius, fill="#00c292")

    wallet_x = size * 0.28
    wallet_y = size * 0.34
    wallet_w = size * 0.44
    wallet_h = size * 0.32
    draw.rounded_rectangle(
        (wallet_x, wallet_y, wallet_x + wallet_w, wallet_y + wallet_h),
        radius=size // 18,
        fill="#004935",
    )
    draw.rounded_rectangle(
        (wallet_x + size * 0.08, wallet_y + size * 0.08, wallet_x + wallet_w, wallet_y + wallet_h),
        radius=size // 20,
        fill="#f4fbf5",
    )
    dot_r = size // 28
    dot_x = wallet_x + wallet_w - size * 0.10
    dot_y = wallet_y + wallet_h * 0.5
    draw.ellipse((dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r), fill="#00c292")

    image.save(ICON_DIR / f"icon-{size}.png")


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    for size in (192, 512):
        draw_icon(size)


if __name__ == "__main__":
    main()
