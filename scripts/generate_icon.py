"""Generate installer/icon.ico if it doesn't exist (fallback for CI/local builds)."""

from pathlib import Path

from PIL import Image, ImageDraw


def generate_icon(output_path: Path) -> None:
    sizes = [256, 128, 64, 48, 32, 16]
    images = []

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        padding = max(1, size // 16)
        draw.ellipse([padding, padding, size - padding, size - padding], fill=(30, 140, 255))

        mic_w, mic_h = size // 5, size // 3
        mic_x, mic_y = (size - mic_w) // 2, size // 4
        draw.rounded_rectangle(
            [mic_x, mic_y, mic_x + mic_w, mic_y + mic_h],
            radius=mic_w // 2,
            fill=(255, 255, 255, 240),
        )

        images.append(img)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        str(output_path),
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print(f"Generated {output_path}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    generate_icon(project_root / "installer" / "icon.ico")
